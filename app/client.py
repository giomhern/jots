import requests 

class JotsClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self, idempotency_key: str | None = None):
        headers = {
            "Content-Type": "application/json", 
            "X-API-Key": self.api_key
        }

        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        
        return headers 
    
    def create_customer(self, name: str, email: str, idempotency_key: str | None = None):
        url = f"{self.base_url}/customers"
        payload = {"name": name, "email": email}
        resp = requests.post(url, json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()
    
    def credit_customer(self, customer_id: str, amount: int, description: str | None = None, idempotency_key: str | None = None):

        url = f"{self.base_url}/customers/{customer_id}/credit"
        payload = {"amount": amount}
        if description is not None:
            payload["description"] = description 
        resp = requests.post(url=url, json=payload, headers = self._headers(idempotency_key=idempotency_key))
        resp.raise_for_status()
        return resp.json()
    
    def create_charge(self, customer_id: str, amount: int, description: str | None = None, idempotency_key: str | None = None):
        url = f"{self.base_url}/charges"
        payload = {
            "customer_id": customer_id,
            "amount": amount,
        }
        if description is not None:
            payload["description"] = description
        resp = requests.post(url, json=payload, headers=self._headers(idempotency_key))
        resp.raise_for_status()
        return resp.json()
    
    def list_transactions(self, customer_id: str, limit: int = 50):
        url = f"{self.base_url}/customers/{customer_id}/transactions"
        params = {"limit": limit}
        resp = requests.get(url, params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()
    
if __name__ == "__main__":
    client = JotsClient("http://127.0.0.1:5000", "test_secret_123")

    ada = client.create_customer("Ada Lovelace", "ada@example.com", idempotency_key="cust-ada-1")
    print("Customer:", ada)

    updated = client.credit_customer(ada["id"], 5000, "Initial top-up", idempotency_key="credit-ada-1")
    print("After credit:", updated)

    charge = client.create_charge(ada["id"], 2000, "Test charge", idempotency_key="charge-ada-1")
    print("Charge:", charge)

    txns = client.list_transactions(ada["id"], limit=10)
    print("Transactions:", txns)