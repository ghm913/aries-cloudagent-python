from prometheus_client import start_http_server, Gauge
import time
import requests

# Define your metrics
total_messages_received = Gauge('acapy_received_messages_total', 'Total messages received by ACA-Py')

def fetch_metrics():
    while True:
        try:
            # Replace this with the actual API call to ACA-Py
            response = requests.get('http://localhost:8021/status')  # Adjust the URL as needed
            data = response.json()

            # Extract and set metrics
            total_messages_received.set(data['result']['total_messages_received'])  # Adjust the JSON path as needed

        except Exception as e:
            print(f"Error fetching metrics: {e}")

        time.sleep(15)

if __name__ == "__main__":
    # Start the Prometheus metrics server
    start_http_server(8080)
    # Fetch and update metrics
    fetch_metrics()
