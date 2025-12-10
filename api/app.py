# app.py 

from flask import Flask, json, request, jsonify
from datetime import datetime 
import uuid 

app = Flask(__name__)

# --- helper functions ---

def iso_utc_now() -> str:
    """Return current time in ISO8601 UTC with 'Z' suffix."""
    return datetime.utcnow().isoformat() + "Z"

def error_response(message: str, status_code: int, error_type: str = "invalid_request"):
    """
    Return a standardized error response.

    Example:
    {
      "error": {
        "type": "invalid_request",
        "message": "name is required"
      }
    }
    """

    payload = {
        "error": {
            "type": error_type, 
            "message": message
        }
    }

    return jsonify(payload), status_code

def validate_customer_payload(data: dict):
    """
    Validate the JSON payload for creating a customer.

    Returns:
        (is_valid: bool, error_message: str | None)
    """
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object."
    
    name = data.get("name")
    email = data.get("email")

    if not isinstance(name, str) or not name.strip():
        return False, "Name is required and must be a non-empty string."
    
    if not isinstance(email, str) and not email.strip():
        return False, "Email is required and must be non-empty string."
    
    if "@" not in email:
        return False, "Email must contain '@'."
    
    return True, None


# in-memory database
CUSTOMERS = {} 

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/customers", methods=["POST"])
def create_customer():
    """
    Create a new customer.

    Expected JSON body:
    {
      "name": "Ada Lovelace",
      "email": "ada@example.com"
    }

    Response (201):
    {
      "id": "...",
      "name": "...",
      "email": "...",
      "created_at": "..."
    }
    """

    data = request.get_json(silent=True)
    is_valid, error_msg = validate_customer_payload(data=data)

    if not is_valid:
        return error_response(error_msg, 400, "invalid_request")
    
    customer_id = str(uuid.uuid4())

    customer = {
        "id": customer_id,
        "name": data["name"].strip(), 
        "email": data["email"].strip(), 
        "created_at": iso_utc_now()
    }

    CUSTOMERS[customer_id] = customer 
    return jsonify(customer), 201

@app.route("/customers", methods=["GET"])
def list_customers():
    """
    List all customers.

    Response (200):
    {
      "data": [
        {...customer1...},
        {...customer2...}
      ]
    }
    """

    customers_list = list(CUSTOMERS.values())
    return jsonify({"data": customers_list}), 200

@app.route("/customers/<customer_id", methods=["GET"])
def get_customer(customer_id):
    """
    Retrieve a single customer by ID.

    Response (200):
      {...customer...}

    Response (404):
    {
      "error": {
        "type": "not_found",
        "message": "Customer not found"
      }
    }
    """

    customer = CUSTOMERS.get(customer_id)

    if customer is None:
        return error_response("Customer not found", 404, "not_found")
    
    return jsonify(customer), 200



if __name__ == "__main__":
    app.run(debug=True)