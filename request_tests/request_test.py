import requests
import time

# Define the base URLs for Anton and Bob
anton_base_url = "http://localhost:8021"
bob_base_url = "http://localhost:8031"

# Helper function to handle responses
def handle_response(response):
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.json()

# 1. Get Anton's connections
anton_connections_url = f"{anton_base_url}/connections"
anton_connections_response = requests.get(anton_connections_url, headers={"Accept": "application/json"})
anton_connections = handle_response(anton_connections_response)["results"]

# Delete each connection
for connection in anton_connections:
    connection_id = connection["connection_id"]
    delete_url = f"{anton_base_url}/connections/{connection_id}"
    delete_response = requests.delete(delete_url, headers={"Content-Type": "application/json"})
    print(f"Deleted connection {connection_id}: {delete_response.status_code}")
    time.sleep(1)  # Wait for a short period to ensure the deletion is processed

# 2. Get Bob's connections
bob_connections_url = f"{bob_base_url}/connections"
bob_connections_response = requests.get(bob_connections_url, headers={"Accept": "application/json"})
bob_connections = handle_response(bob_connections_response)

# 3. Bob sends a connection request to Anton
bob_create_request_url = f"{bob_base_url}/didexchange/create-request?their_public_did=NyaE9SFSneSNRq6Ch8N9Pt&alias=Anton"
bob_create_request_response = requests.post(bob_create_request_url, headers={"Accept": "application/json"})
bob_connection_id = handle_response(bob_create_request_response)["connection_id"]

# Wait for the connection request to appear in Anton's connections
time.sleep(2)  # Wait for a short period to ensure the request is processed

# 4. Anton retrieves the connection request
# anton_pending_connections_url = f"{anton_base_url}/connections?state=request"
# anton_pending_connections_response = requests.get(anton_pending_connections_url, headers={"Accept": "application/json"})
# anton_connection_id = handle_response(anton_pending_connections_response)["results"][-1]["connection_id"]

# 5. Anton accepts the connection request
# anton_accept_request_url = f"{anton_base_url}/didexchange/{anton_connection_id}/accept-request"
# anton_accept_request_response = requests.post(anton_accept_request_url, headers={"Content-Type": "application/json"})
# handle_response(anton_accept_request_response)

# # Wait for the connection state to become active
# time.sleep(2)  # Wait for a short period to ensure the state is updated

# 7. Anton sends a message to Bob
anton_send_message_url = f"{anton_base_url}/connections/{bob_connection_id}/send-message"
message_payload = {
    "content": "Hallo Bob"
}
anton_send_message_response = requests.post(anton_send_message_url, json=message_payload, headers={"Content-Type": "application/json"})
handle_response(anton_send_message_response)

print("Message sent from Anton to Bob successfully.")