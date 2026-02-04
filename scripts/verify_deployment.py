import requests
import sys

BASE_URL = "http://localhost:8001"
EMAIL = "system_verification_3@example.com"
PASSWORD = "Password123!"

def log(msg):
    print(f"[TEST] {msg}")

def run_test():
    # 1. Register
    log(f"Registering user {EMAIL}...")
    reg_payload = {
        "email": EMAIL,
        "password": PASSWORD,
        "first_name": "Verification",
        "last_name": "Bot"
    }
    try:
        r = requests.post(f"{BASE_URL}/api/auth/register", json=reg_payload)
        if r.status_code == 201:
            log("✅ Registration Successful")
        elif r.status_code == 400 and "already exists" in r.text:
            log("ℹ️ User already exists (Skipping registration)")
        else:
            log(f"❌ Registration Failed: {r.status_code} {r.text}")
            return
    except Exception as e:
        log(f"❌ Connection Failed: {e}")
        return

    # 2. Login
    log("Logging in...")
    login_payload = {
        "email": EMAIL,
        "password": PASSWORD
    }
    # Using JSON login as per auth.py definition
    r = requests.post(f"{BASE_URL}/api/auth/login", json=login_payload)
    
    if r.status_code != 200:
        log(f"❌ Login Failed: {r.status_code} {r.text}")
        return
    
    # Auth response structure might be { "user": ..., "tokens": { "access_token": ... } }
    data = r.json()
    tokens = data.get("tokens", {})
    token = tokens.get("access_token")

    if not token:
        # Fallback in case response model is flat (unlikely based on code reading)
        token = data.get("access_token")
    
    
    if not token:
        log(f"❌ No token found in response: {data.keys()}")
        return
    
    # Extract User ID from login response
    user_info = data.get("user", {})
    user_id = user_info.get("id")
    if not user_id:
        log("❌ No User ID found in response")
        return

    log(f"✅ Login Successful (Token: {token[:10]}... UserID: {user_id})")
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Transaction
    log("Creating transaction...")
    trans_payload = {
        "amount": 125.50,
        "date": "2024-01-30",
        "description": "Weekly Groceries at Whole Foods",
        "type": "EXPENSE",
        "source": "MANUAL",
        "category": "Groceries" # Optional, to test if it accepts it or auto-categorizes
    }
    # Append user_id to Query String
    r = requests.post(f"{BASE_URL}/api/transactions/?user_id={user_id}", json=trans_payload, headers=headers)
    if r.status_code == 200 or r.status_code == 201:
        log("✅ Transaction Created")
        data = r.json()
        log(f"   Category Assigned: {data.get('category')}")
        log(f"   Confidence: {data.get('confidence_score')}")
    else:
        log(f"❌ Create Transaction Failed: {r.status_code}")
        log(f"   Response: {r.text}")

    # 4. Get Dashboard/Stats
    log("Fetching Transactions...")
    # Append user_id to Query String
    r = requests.get(f"{BASE_URL}/api/transactions/?user_id={user_id}", headers=headers)
    if r.status_code == 200:
        count = len(r.json().get('transactions', [])) # Response model is TransactionListResponse with 'transactions' key
        log(f"✅ Picked up {count} transactions")
    else:
        log(f"❌ Fetch Transactions Failed: {r.status_code} {r.text}")

if __name__ == "__main__":
    run_test()
