from flask import Flask, jsonify
import os
import json
import shutil
from elasticsearch import Elasticsearch

app = Flask(__name__)

SOURCE_DIR = '/apps/c1/scripts/data/source'
PROCESSED_DIR = '/apps/c1/scripts/data/processed'
ES_HOST = "http://localhost:9200"
INDEX_NAME = "rbcapp_application_status"

es = Elasticsearch("https://devlogs.es.elk.dev01.lv1.c1b.corp:9243",basic_auth=("metricCollector", "Link.360"), verify_certs=False)


   # basic_auth=("metricCollector", "Link.360")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def process_json_files():
    processed_files = []
    for filename in os.listdir(SOURCE_DIR):
        if filename.endswith(".json"):
            file_path = os.path.join(SOURCE_DIR, filename)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)

                # Send to Elasticsearch
                es.index(index=INDEX_NAME, body=data)

                shutil.move(file_path, os.path.join(PROCESSED_DIR, filename))
                processed_files.append(filename)
                print(f"Processed: {filename}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")
    return processed_files

# --- Endpoints ---

@app.route('/add', methods=['POST'])
def trigger_add():
    """Trigger processing of JSON files."""
    files = process_json_files()
    return jsonify({"status": "success", "processed_files": files}), 200


@app.route('/healthcheck', methods=['GET'])
def get_all_health():
    """Return status of all services from latest data."""
    # Query latest document for each service
    query = {
                "size": 1000,
                "query": {
                    "match_all": {}
                    },
                "collapse": {
                    "field": "service_name.keyword",
                    "inner_hits": {
                        "name": "latest_per_service",
                        "size": 1,
                        "sort": [
                            { "@timestamp": { "order": "desc" } }
                            ]
                        }
                    },
                "sort": [
                    { "service_name.keyword": "asc" }
                    ]
            }

    response = es.search(index=INDEX_NAME, body=query)
    results = {}
    for bucket in response['aggregations']['latest_services']['buckets']:
        service_name = bucket['key']
        latest_status = bucket['latest_doc']['hits']['hits'][0]['_source']['status']
        results[service_name] = latest_status

    return jsonify(results), 200

@app.route('/healthcheck/<serviceName>', methods=['GET'])
def get_service_health(serviceName):
    """Return status of a specific service from latest data."""
    query = {
        "size": 1,
        "query": {
            "term": { "serviceName.keyword": serviceName }
        },
        "sort": [{"@timestamp": {"order": "desc"}}]
    }

    response = es.search(index=INDEX_NAME, body=query)
    if response['hits']['hits']:
        status = response['hits']['hits'][0]['_source']['status']
        return jsonify({"serviceName": serviceName, "status": status}), 200
    else:
        return jsonify({"error": "Service not found"}), 404

if __name__ == '__main__':
    app.run(port=40401)
