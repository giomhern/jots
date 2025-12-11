# app.py 

from flask import Flask, json, request, jsonify
from functools import wraps
from datetime import datetime 
import uuid 

app = Flask(__name__)

# --- global vars ---

CUSTOMERS = {} 
CHARGES = {}
TRANSACTIONS = []
IDEMPOTENCY_STORE = {}

VALID_API_KEYS = {
    "test_secret_123"
}

# --- global vars ---


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

def validate_add_funds_payload(data: dict):
    """
    Validate the JSON payload for adding funds.

    Returns:
        (is_valid: bool, error_message: str | None)
    """
      
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object."
    
    amount = data.get("amount")
    description = data.get("description")


    if not isinstance(amount, int) or amount <= 0:
        return False, "Amount is required, must to be an integer and must be greater than 0."
    
    if description is not None:
        if not isinstance(description, str) or not description.strip():
            return False, "Description must be non-empty string."

    
    return True, None 


def get_customer_or_404(customer_id: str):
    customer = CUSTOMERS.get(customer_id)

    if customer is None:
       return None, error_response(f"Customer with {customer_id} not found.", status_code=404, error_type="not_found")
    
    return customer, None

def record_transaction(customer_id: str, kind: str, amount: int, balance_after: int, description: str | None = None, related_id: str | None = None):
    transaction = {
        "id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "type": kind,  # "credit" or "charge"
        "amount": amount,
        "description": description,
        "balance_after": balance_after,
        "related_id": related_id,
        "created_at": iso_utc_now(),
    }

    TRANSACTIONS.append(transaction)

    return transaction


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")

        if api_key not in VALID_API_KEYS:
            return error_response("Invalid or missing API key.", 401, "unauthorized")
        return fn(*args, **kwargs)
    return wrapper 

def check_idempotency():
    """
    Check if this request has an Idempotency-Key that we've seen before.
    If yes, return (response, True).
    If no key or not seen before, return (None, False).
    """

    key = request.headers.get("Idempotency")

    if not key:
        return None, False
    
    entry = IDEMPOTENCY_STORE.get(key)

    if entry is None:
        return None, False 
    
    return (jsonify(entry["body"], entry["status_code"])), True 

def store_idempotent_response(body: dict, status_code: int):
    """
    Store the response for the current request's Idempotency-Key, if present.
    """

    key = request.headers.get("Idempotency-Key")
    if not key:
        return
    
    IDEMPOTENCY_STORE[key] = {
        "body": body, 
        "status_code": status_code
    }

    
# --- helper functions ---

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/customers", methods=["POST"])
@require_api_key
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
        "created_at": iso_utc_now(), 
        "balance": 0
    }

    CUSTOMERS[customer_id] = customer 
    return jsonify(customer), 201

@app.route("/customers", methods=["GET"])
@require_api_key
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

@app.route("/customers/<customer_id>", methods=["GET"])
@require_api_key
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

@app.route("/customers/<customer_id>/credit", methods=["POST"])
@require_api_key
def credit_customer(customer_id):
    """
    Add funds/credits to a customer's balance.

    Body:
    {
      "amount": 5000,
      "description": "optional"
    }
    """

    replay, is_replay = check_idempotency()
    if is_replay:
        return replay

    customer, error = get_customer_or_404(customer_id=customer_id)
    if error is not None:
        return error 
    
    data = request.get_json(silent=True)

    is_valid, error = validate_add_funds_payload(data=data)
    if not is_valid:
        return error_response(error, 400, "invalid_request")
    
    amount = data.get("amount")
    customer["balance"] += amount 

    balance_after = customer["balance"]

    description = data.get("description")

    record_transaction(
        customer_id=customer_id, 
        kind="credit", 
        amount=amount, 
        balance_after=balance_after, 
        description=description, 
        related_id=None
    )

    return jsonify(customer), 200
    
@app.route("/charges", methods=["POST"])
@require_api_key
def create_charge():
    """
    Create a charge against a customer's balance.

    Body:
    {
      "customer_id": "<id>",
      "amount": 2500,
      "description": "optional"
    }
    """

    replay, is_replay = check_idempotency()
    if is_replay:
        return replay

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("Request body must be a JSON object.", 400, "invalid_request")

    customer_id = data.get("customer_id")
    description = data.get("description")
    amount = data.get("amount")

    customer, error = get_customer_or_404(customer_id=customer_id)

    if error is not None:
        return error
    
    if not isinstance(amount, int) or amount <= 0:
        return error_response("Amount must be a non-negative integer.", 400, "invalid_request")
    
    if amount > customer['balance']:
        return error_response("Amount exceeds customer's balance.", 400, "insufficient_funds")
    
    customer['balance'] -= amount
    balance_after = customer['balance']

    charge_id = str(uuid.uuid4())
    charge = {
        "id": charge_id, 
        "customer_id": customer_id, 
        "amount": amount, 
        "description": description, 
        "created_at": iso_utc_now(), 
        "status": "succeeded"
    }

    CHARGES[charge_id] = charge

    record_transaction(
        customer_id=customer_id, 
        kind="charge", 
        amount=amount, 
        balance_after=balance_after, 
        description=description, 
        related_id=charge_id
    )

    return jsonify(charge), 201


@app.route("/customers/<customer_id>/transactions", methods=["GET"])
@require_api_key
def list_customer_transactions(customer_id):
    """
    List a customer's transactions (ledger entries).

    Optional query params:
      - limit: int, default 50
    """

    customer, err = get_customer_or_404(customer_id=customer_id)

    if customer is None:
        return err 
    
    limit_param = request.args.get("limit")

    try:
        limit = int(limit_param) if limit_param is not None else 50
    except ValueError:
        return error_response("Limit must be an integer.", 400, "invalid_request")
    
    if limit <= 0:
        return error_response("Limit must be positive.", 400, "invalid_request")
    
    customer_txns = [t for t in TRANSACTIONS if t['customer_id'] == customer_id]
    customer_txns.sort(key=lambda t: t["created_at"], reverse=True)

    customer_txns[:limit]

    return jsonify({"data": customer_txns}), 200


if __name__ == "__main__":
    app.run(debug=True)