# RBC App Monitoring — Project Overview

This project contains scripts to monitor RHEL services, collect metrics, ingest data into Elasticsearch, expose REST health check endpoints, and automate server management with Ansible.

---

## Project Structure

```
/
├── monitorin.py                  # Checks service status and writes JSON payloads
├── webservice.py                 # Flask REST API — ingests JSON into Elasticsearch
├── logstashMetricCollector.pl    # Collects Logstash pipeline metrics and pushes to Elasticsearch
├── field_manipulation.py         # Filters real estate CSV by price per sqft
├── sales-data.csv                # Input data for field_manipulation.py
├── assignment.yaml               # Ansible playbook for server monitoring and management
├── inventory                     # Ansible inventory — defines the three monitored hosts
└── README.md
```

---

## How the Scripts Fit Together

```
monitorin.py                  logstashMetricCollector.pl
     |                                    |
     | writes JSON files                  | pushes metrics via bulk API
     v                                    v
/apps/c1/scripts/data/source         Elasticsearch
     |
     | POST /add
     v
webservice.py  <------  assignment.yaml (check-status action)
     |
     | GET /healthcheck
     v
  Returns service UP/DOWN status
```

---

## 1. monitorin.py

Checks the status of four services using `systemctl`, builds a JSON payload for each, and writes them to a source directory where `webservice.py` will pick them up.

### Services Monitored

`logstash`, `httpd`, `rabbitMQ`, `postgreSQL`

### Configuration

| Variable | Default | Description |
|---|---|---|
| `SERVICES` | See above | List of systemctl service names to check |
| `OUTPUT_DIR` | `/apps/c1/scripts/data/source` | Where JSON files are written |

### Running

```bash
python monitorin.py
```

### Output

One JSON file per service, written to `OUTPUT_DIR`. Example filename:

```
httpd-status-@2026-05-09T10-30-00Z.json
```

Example file content:

```json
{
  "service_name": "httpd",
  "service_status": "UP",
  "host_name": "host1",
  "@timestamp": "2026-05-09T10:30:00Z"
}
```

### Recommended Setup

Run as a cron job so status is continuously updated:

```bash
# Run every 5 minutes
*/5 * * * * /usr/bin/python3 /apps/c1/scripts/monitorin.py
```

---

## 2. webservice.py

A Flask REST API that picks up JSON files written by `monitorin.py`, indexes them into Elasticsearch, and exposes endpoints to check service health.

### Prerequisites

```bash
pip install flask elasticsearch
```

### Configuration

Edit these at the top of the file:

| Variable | Description |
|---|---|
| `SOURCE_DIR` | Folder to read incoming JSON files from |
| `PROCESSED_DIR` | Folder to move processed files to |
| `INDEX_NAME` | Elasticsearch index name |
| ES connection (line 14) | Update host URL, username, and password |

### Running

```bash
python webservice.py
```

Starts on port **40401**.

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/add` | Reads JSON files from `SOURCE_DIR`, indexes them into Elasticsearch, moves them to `PROCESSED_DIR` |
| `GET` | `/healthcheck` | Returns the latest status of all services |
| `GET` | `/healthcheck/<serviceName>` | Returns the status of a specific service |

### Example Requests

```bash
# Ingest pending JSON files
curl -X POST http://localhost:40401/add

# Get all service statuses
curl http://localhost:40401/healthcheck

# Get one service
curl http://localhost:40401/healthcheck/httpd
```

### Example Response

```json
{
  "httpd": "UP",
  "rabbitMQ": "DOWN",
  "postgreSQL": "UP"
}
```

---

## 3. logstashMetricCollector.pl

A Perl script that collects Logstash pipeline metrics (events in/out, queue backlog, errors, disk usage) and bulk-indexes them into Elasticsearch.

### Prerequisites

- `curl` and `jq` installed on the host
- `perl` installed
- Logstash running and exposing its API on port `9600`

### Configuration

Edit these variables at the top of the script:

| Variable | Description |
|---|---|
| `$log_window` | How far back to scan journalctl for errors (default: `5 minutes ago`) |
| `$queue_path` | Path to the Logstash queue directory |
| `$api_url` | Logstash node stats API URL |
| `$user` / `$password` | Elasticsearch credentials |
| `$index_name` | Elasticsearch index to write metrics to |
| `$Monitorhost` | Elasticsearch destination host URL |
| `$cluster` / `$location` | Labels added to every metric document |

### Running

```bash
perl logstashMetricCollector.pl
```

### What It Collects Per Pipeline

| Field | Description |
|---|---|
| `event_in` / `event_out` | Events processed |
| `backlog` | Queue event count |
| `error_count` | Indexing errors in the last 5 minutes |
| `reload_success` / `reload_failure` | Pipeline reload counts |
| `backlog_disksize` | Queue disk size in MB |

### Recommended Setup

```bash
# Run every 5 minutes via cron
*/5 * * * * /usr/bin/perl /apps/c1/scripts/logstashMetricCollector.pl
```

---

## 4. field_manipulation.py

Reads a real estate sales CSV, calculates the average price per square foot, and outputs a filtered CSV containing only properties sold below that average.

### Prerequisites

```bash
pip install pandas
```

### Input File

`sales-data.csv` must be in the same directory. Required columns:

| Column | Description |
|---|---|
| `price` | Sale price |
| `sq__ft` | Square footage (rows with 0 are excluded) |

### Running

```bash
python field_manipulation.py
```

### Output

`below_average_price_per_sqft.csv` — created in the same directory.

### Sample Console Output

```
Total properties loaded: 985
Properties with valid sqft: 814
Average price per sqft: $145.67
Properties below average: 470
Done — results saved to 'below_average_price_per_sqft.csv'
```

---

## 5. assignment.yaml + inventory (Ansible)

An Ansible playbook that manages and monitors the three RHEL servers. The behaviour is controlled by passing an `action` variable at runtime.

### Server Layout

| Host | IP | Service |
|---|---|---|
| host1 | 192.168.1.10 | httpd (Apache) |
| host2 | 192.168.1.20 | RabbitMQ |
| host3 | 192.168.1.30 | PostgreSQL |

### Prerequisites

```bash
pip install ansible
ansible-galaxy collection install community.general
```

SSH key-based access must be configured from the Ansible control node to all three hosts.

### Actions

#### verify_install

Checks whether each service is installed on its allocated host. Installs and starts `httpd` on `host1` if it is missing (used as the install example).

```bash
ansible-playbook assignment.yaml -i inventory -e action=verify_install
```

#### check-disk

Checks disk usage on all three servers. Sends an alert email to `anudeepsty@gmail.com` for any filesystem over **80%**.

```bash
ansible-playbook assignment.yaml -i inventory -e action=check-disk
```

> **SMTP note:** The playbook assumes a local mail relay is running on port 25 of the Ansible control node. To use Gmail or another external SMTP server, update the `host`, `port`, `username`, `password`, and `secure` fields inside the `Send alert email` task.

#### check-status

Calls the `/healthcheck` endpoint of `webservice.py` and lists any services currently reporting as DOWN.

```bash
ansible-playbook assignment.yaml -i inventory -e action=check-status
```

> `webservice.py` must be running before executing this action.

### Updating the Inventory

Replace the placeholder IPs and usernames with real values before running:

```ini
[webservers]
host1 ansible_host=<real-ip> ansible_user=<ssh-user>
```

---

## Dependencies Summary

| Script | Language | Dependencies |
|---|---|---|
| `monitorin.py` | Python 3 | Standard library only |
| `webservice.py` | Python 3 | `flask`, `elasticsearch` |
| `logstashMetricCollector.pl` | Perl | `curl`, `jq` (system) |
| `field_manipulation.py` | Python 3 | `pandas` |
| `assignment.yaml` | Ansible | `ansible`, `community.general` |

Install all Python dependencies:

```bash
pip install flask elasticsearch pandas
```
