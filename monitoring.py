import json
import socket
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

SERVICES =["logstash","httpd","rabbitMQ","postgreSQL"]
OUTPUT_DIR = Path("/apps/c1/scripts/data/source")

def is_service_up(name):
    result = subprocess.run(["systemctl","is-active", name],capture_output=True,text=True)
    return result.returncode==0

def build_payload(service_name,host_name):
    return{
            "service_name": service_name,
            "service_status": "UP" if is_service_up(service_name) else "DOWN",
            "host_name": host_name,
            "@timestamp": datetime.utcnow().isoformat() + "Z"
            }

def write_payload(payload, out_dir):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    filename= f"{payload['service_name']}-status-@{ts}.json"
    path = out_dir / filename
    path.write_text(json.dumps(payload, indent=2))
    return path

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname()

    any_down = False
    for service in SERVICES:
        payload =build_payload(service,host)
        path = write_payload(payload,OUTPUT_DIR)

    #rc = is_service_up("logstash")
    #print(f"logstash status: {status} (returncode={rc})")

if __name__ == "__main__":
    sys.exit(main())
