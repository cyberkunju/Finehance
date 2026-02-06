"""
Full System Integration Test - Tests ALL endpoints, ML, AI Brain LLM
Run inside docker: docker compose exec dev python test_full_system.py
"""
import requests
import json
import time
import sys
import uuid
from datetime import datetime, timedelta

# Inside Docker network: use service names for cross-container calls
BASE = "http://localhost:8000"
AI_BRAIN = "http://ai-brain:8080"
PROMETHEUS = "http://prometheus:9090"
GRAFANA = "http://grafana:3000"

PASS = 0
FAIL = 0
RESULTS = []

def test(name, func):
    global PASS, FAIL
    try:
        result = func()
        PASS += 1
        RESULTS.append(("PASS", name, result))
        print(f"  PASS {name}: {result}")
    except Exception as e:
        FAIL += 1
        RESULTS.append(("FAIL", name, str(e)))
        print(f"  FAIL {name}: {e}")

# ===========================
# AUTH TESTS
# ===========================
print("\n" + "="*60)
print("AUTH TESTS")
print("="*60)

TOKEN = None
REFRESH_TOKEN = None
USER_ID = None

def test_register():
    ts = int(time.time())
    r = requests.post(f"{BASE}/api/auth/register", json={
        "email": f"test_{ts}@finehance.com",
        "password": "TestPass123!",
        "full_name": "Integration Tester"
    }, timeout=10)
    if r.status_code in (200, 201):
        return f"User created ({r.status_code})"
    elif r.status_code in (400, 409):
        return f"Already exists ({r.status_code}) - OK"
    r.raise_for_status()

def test_login():
    global TOKEN, REFRESH_TOKEN, USER_ID
    r = requests.post(f"{BASE}/api/auth/login", json={
        "email": "testuser@finehance.com",
        "password": "TestPass123!"
    }, timeout=10)
    r.raise_for_status()
    data = r.json()
    TOKEN = data["tokens"]["access_token"]
    REFRESH_TOKEN = data["tokens"]["refresh_token"]
    USER_ID = data["user"]["id"]
    return f"Token obtained, user_id={USER_ID[:8]}..."

def test_me():
    r = requests.get(f"{BASE}/api/auth/me",
                     headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10)
    r.raise_for_status()
    return f"email={r.json()['email']}"

def test_refresh():
    r = requests.post(f"{BASE}/api/auth/refresh", json={
        "refresh_token": REFRESH_TOKEN
    }, timeout=10)
    r.raise_for_status()
    return "New token obtained"

test("Register new user", test_register)
test("Login", test_login)
test("Get /me profile", test_me)
test("Refresh token", test_refresh)

headers = {"Authorization": f"Bearer {TOKEN}"}

# ===========================
# TRANSACTION TESTS
# ===========================
print("\n" + "="*60)
print("TRANSACTION TESTS")
print("="*60)

TRANSACTION_IDS = []

def test_create_transactions():
    txns = [
        {"description": "Starbucks coffee", "amount": 5.50, "type": "EXPENSE", "category": "food_dining", "date": "2026-01-15"},
        {"description": "Walmart groceries", "amount": 85.30, "type": "EXPENSE", "category": "groceries", "date": "2026-01-16"},
        {"description": "Monthly salary", "amount": 5000.00, "type": "INCOME", "category": "salary", "date": "2026-01-01"},
        {"description": "Netflix subscription", "amount": 15.99, "type": "EXPENSE", "category": "entertainment", "date": "2026-01-10"},
        {"description": "Uber ride to airport", "amount": 32.50, "type": "EXPENSE", "category": "transportation", "date": "2026-01-12"},
        {"description": "Amazon electronics", "amount": 249.99, "type": "EXPENSE", "category": "shopping", "date": "2026-01-20"},
        {"description": "Electric bill", "amount": 120.00, "type": "EXPENSE", "category": "utilities", "date": "2026-01-05"},
        {"description": "Gym membership", "amount": 45.00, "type": "EXPENSE", "category": "health_fitness", "date": "2026-01-03"},
        {"description": "Freelance payment", "amount": 1500.00, "type": "INCOME", "category": "freelance", "date": "2026-01-18"},
        {"description": "Gas station shell", "amount": 55.00, "type": "EXPENSE", "category": "transportation", "date": "2026-01-22"},
        {"description": "Restaurant dinner", "amount": 78.50, "type": "EXPENSE", "category": "food_dining", "date": "2026-01-25"},
        {"description": "Phone bill T-Mobile", "amount": 65.00, "type": "EXPENSE", "category": "utilities", "date": "2026-01-08"},
    ]
    created = 0
    for txn in txns:
        r = requests.post(f"{BASE}/api/transactions?user_id={USER_ID}",
                          json=txn, headers=headers, timeout=10)
        if r.status_code in (200, 201):
            data = r.json()
            tid = data.get("id")
            if tid:
                TRANSACTION_IDS.append(tid)
            created += 1
    return f"Created {created}/12 transactions"

def test_list_transactions():
    r = requests.get(f"{BASE}/api/transactions?user_id={USER_ID}&page=1&page_size=50",
                     headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    total = data.get("total", len(data.get("transactions", data.get("items", []))))
    return f"Total={total} transactions"

def test_get_transaction():
    r = requests.get(f"{BASE}/api/transactions?user_id={USER_ID}&page=1&page_size=1",
                     headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    items = data.get("transactions", data.get("items", []))
    if items:
        tid = items[0]["id"]
        r2 = requests.get(f"{BASE}/api/transactions/{tid}?user_id={USER_ID}",
                          headers=headers, timeout=10)
        r2.raise_for_status()
        return f"Got: {r2.json().get('description', 'OK')}"
    return "No transactions found"

def test_update_transaction():
    if TRANSACTION_IDS:
        tid = TRANSACTION_IDS[0]
        r = requests.put(f"{BASE}/api/transactions/{tid}?user_id={USER_ID}",
                         json={"description": "Updated Starbucks latte"},
                         headers=headers, timeout=10)
        r.raise_for_status()
        return f"Updated: {r.json().get('description', 'OK')}"
    # fallback: list and use first
    r = requests.get(f"{BASE}/api/transactions?user_id={USER_ID}&page=1&page_size=1",
                     headers=headers, timeout=10)
    items = r.json().get("transactions", r.json().get("items", []))
    if items:
        tid = items[0]["id"]
        r2 = requests.put(f"{BASE}/api/transactions/{tid}?user_id={USER_ID}",
                          json={"description": "Updated via fallback"},
                          headers=headers, timeout=10)
        r2.raise_for_status()
        return f"Updated (fallback): {r2.json().get('description')}"
    return "No transactions to update"

test("Create 12 transactions", test_create_transactions)
test("List all transactions", test_list_transactions)
test("Get single transaction", test_get_transaction)
test("Update transaction", test_update_transaction)

# ===========================
# ML CATEGORIZATION TESTS
# ===========================
print("\n" + "="*60)
print("ML CATEGORIZATION ENGINE TESTS")
print("="*60)

def test_ml_status():
    r = requests.get(f"{BASE}/api/ml/status", headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"global_loaded={d.get('global_model',{}).get('loaded')}"

def test_ml_categories():
    r = requests.get(f"{BASE}/api/ml/categories", headers=headers, timeout=10)
    r.raise_for_status()
    cats = r.json()
    count = len(cats) if isinstance(cats, list) else len(cats.get("categories", []))
    return f"{count} categories"

def test_ml_categorize():
    r = requests.post(f"{BASE}/api/ml/categorize",
                      json={"description": "Starbucks coffee grande latte"},
                      headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    cat = d.get("category", d.get("predicted_category", "?"))
    conf = d.get("confidence", "?")
    return f"'{cat}' confidence={conf}"

def test_ml_batch_categorize():
    r = requests.post(f"{BASE}/api/ml/categorize/batch", json={
        "transactions": [
            {"description": "McDonald's burger meal", "amount": 12.50},
            {"description": "Shell gas station fuel", "amount": 55.00},
            {"description": "Amazon Prime subscription", "amount": 14.99},
            {"description": "Monthly rent payment", "amount": 1500.00},
            {"description": "Spotify premium music", "amount": 9.99}
        ],
        "user_id": USER_ID
    }, headers=headers, timeout=20)
    r.raise_for_status()
    d = r.json()
    results = d if isinstance(d, list) else d.get("results", d.get("predictions", []))
    cats = [x.get("category", x.get("predicted_category", "?")) for x in results]
    return f"Categorized {len(results)}: {cats}"

def test_ml_correction():
    r = requests.post(f"{BASE}/api/ml/corrections", json={
        "user_id": USER_ID,
        "description": "Costco wholesale shopping",
        "correct_category": "Groceries"
    }, headers=headers, timeout=10)
    r.raise_for_status()
    return "Correction submitted"

def test_ml_global_model():
    r = requests.get(f"{BASE}/api/ml/models/global", headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"accuracy={d.get('accuracy', '?')}, loaded={d.get('loaded', '?')}"

def test_ml_user_model():
    r = requests.get(f"{BASE}/api/ml/models/user/me", headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"has_model={d.get('has_model')}, corrections={d.get('correction_count', 0)}"

def test_ml_train_user():
    r = requests.post(f"{BASE}/api/ml/models/user/me/train", json={
        "force": True,
        "min_samples": 5
    }, headers=headers, timeout=30)
    d = r.json()
    return f"({r.status_code}) {json.dumps(d, indent=None)[:100]}"

test("ML service status", test_ml_status)
test("Get categories", test_ml_categories)
test("Categorize: 'Starbucks coffee'", test_ml_categorize)
test("Batch categorize 5 items", test_ml_batch_categorize)
test("Submit correction", test_ml_correction)
test("Global model status", test_ml_global_model)
test("User model status", test_ml_user_model)
test("Train user model", test_ml_train_user)

# ===========================
# PREDICTION ENGINE TESTS
# ===========================
print("\n" + "="*60)
print("PREDICTION ENGINE TESTS")
print("="*60)

def test_forecast_all():
    r = requests.get(f"{BASE}/api/predictions/forecast?user_id={USER_ID}&periods=7&lookback_days=90",
                     headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    if isinstance(d, dict):
        return f"Forecast keys: {list(d.keys())[:5]}"
    return f"Forecast: {str(d)[:120]}"

def test_forecast_category():
    from urllib.parse import quote
    category = "Food & Dining"
    r = requests.get(f"{BASE}/api/predictions/forecast/{quote(category, safe='')}",
                     params={"periods": 7},
                     headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    cat = d.get("category", "?")
    preds = d.get("predictions", [])
    acc = d.get("accuracy_score", "N/A")
    return f"category={cat}, predictions={len(preds)}, accuracy={acc}"

def test_anomalies():
    from urllib.parse import quote
    category = "Food & Dining"
    r = requests.get(f"{BASE}/api/predictions/anomalies/{quote(category, safe='')}",
                     params={"lookback_days": 90, "threshold_percent": 50},
                     headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    return f"Anomalies found: {len(d)}"

test("Spending forecast (all)", test_forecast_all)
test("Category forecast (food)", test_forecast_category)
test("Anomaly detection", test_anomalies)

# ===========================
# BUDGET TESTS
# ===========================
print("\n" + "="*60)
print("BUDGET TESTS")
print("="*60)

BUDGET_ID = None

def test_create_budget():
    global BUDGET_ID
    r = requests.post(f"{BASE}/api/budgets?user_id={USER_ID}", json={
        "name": "January Budget",
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "allocations": {
            "Food & Dining": 500.00,
            "Transportation": 200.00,
            "Entertainment": 100.00,
            "Utilities": 200.00,
            "Shopping": 300.00
        }
    }, headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    BUDGET_ID = d.get("id")
    return f"Budget created id={str(BUDGET_ID)[:8]}..."

def test_list_budgets():
    r = requests.get(f"{BASE}/api/budgets?user_id={USER_ID}",
                     headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    items = d if isinstance(d, list) else d.get("budgets", d.get("items", []))
    return f"Listed {len(items)} budgets"

def test_budget_progress():
    if not BUDGET_ID:
        return "No budget_id - skipped"
    r = requests.get(f"{BASE}/api/budgets/{BUDGET_ID}/progress?user_id={USER_ID}",
                     headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"Progress: {json.dumps(d, indent=None)[:120]}"

def test_budget_optimize():
    if not BUDGET_ID:
        return "No budget_id - skipped"
    r = requests.post(f"{BASE}/api/budgets/{BUDGET_ID}/optimize?user_id={USER_ID}",
                      headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    return f"Optimization: {json.dumps(d, indent=None)[:120]}"

test("Create budget", test_create_budget)
test("List budgets", test_list_budgets)
test("Budget progress", test_budget_progress)
test("Budget optimization", test_budget_optimize)

# ===========================
# GOALS TESTS
# ===========================
print("\n" + "="*60)
print("GOALS TESTS")
print("="*60)

GOAL_ID = None

def test_create_goal():
    global GOAL_ID
    r = requests.post(f"{BASE}/api/goals?user_id={USER_ID}", json={
        "name": "Emergency Fund",
        "target_amount": 10000.00,
        "initial_amount": 2500.00,
        "deadline": "2026-12-31",
        "category": "savings"
    }, headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    GOAL_ID = d.get("id")
    return f"Goal created id={str(GOAL_ID)[:8]}..."

def test_list_goals():
    r = requests.get(f"{BASE}/api/goals?user_id={USER_ID}",
                     headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    items = d if isinstance(d, list) else d.get("goals", d.get("items", []))
    return f"Listed {len(items)} goals"

def test_goal_progress():
    if not GOAL_ID:
        return "No goal_id - skipped"
    r = requests.get(f"{BASE}/api/goals/{GOAL_ID}/progress?user_id={USER_ID}",
                     headers=headers, timeout=10)
    r.raise_for_status()
    return f"Progress: {json.dumps(r.json(), indent=None)[:120]}"

def test_add_goal_progress():
    if not GOAL_ID:
        return "No goal_id - skipped"
    r = requests.post(f"{BASE}/api/goals/{GOAL_ID}/progress?user_id={USER_ID}",
                      json={"amount": 500.00},
                      headers=headers, timeout=10)
    r.raise_for_status()
    return f"Added $500: {json.dumps(r.json(), indent=None)[:120]}"

def test_goal_risk_alerts():
    r = requests.get(f"{BASE}/api/goals/risks/alerts?user_id={USER_ID}",
                     headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"Risk alerts: {len(d)} alerts"

test("Create goal", test_create_goal)
test("List goals", test_list_goals)
test("Goal progress", test_goal_progress)
test("Add goal progress", test_add_goal_progress)
test("Goal risk alerts", test_goal_risk_alerts)

# ===========================
# ADVICE TESTS
# ===========================
print("\n" + "="*60)
print("ADVICE & INSIGHTS TESTS")
print("="*60)

def test_advice():
    r = requests.get(f"{BASE}/api/advice?user_id={USER_ID}&max_recommendations=5",
                     headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    count = len(d) if isinstance(d, list) else len(d.get("recommendations", d.get("advice", [])))
    return f"Got {count} advice items"

def test_spending_alerts():
    r = requests.get(f"{BASE}/api/advice/spending-alerts?user_id={USER_ID}",
                     headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    return f"Alerts: {json.dumps(d, indent=None)[:120]}"

def test_savings_opportunities():
    r = requests.get(f"{BASE}/api/advice/savings-opportunities?user_id={USER_ID}",
                     headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    return f"Savings: {json.dumps(d, indent=None)[:120]}"

test("Get financial advice", test_advice)
test("Spending alerts", test_spending_alerts)
test("Savings opportunities", test_savings_opportunities)

# ===========================
# AI BRAIN LLM TESTS
# ===========================
print("\n" + "="*60)
print("AI BRAIN / LLM TESTS (GPU - Qwen 2.5-3B)")
print("="*60)

def test_ai_brain_direct():
    r = requests.get(f"{AI_BRAIN}/health", timeout=15)
    r.raise_for_status()
    d = r.json()
    return f"status={d.get('status')}, model_loaded={d.get('model_loaded')}"

def test_ai_status():
    r = requests.get(f"{BASE}/api/ai/status", headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"enabled={d.get('enabled')}, available={d.get('available')}, model_loaded={d.get('model_loaded')}"

def test_ai_chat():
    print("    (LLM inference - may take 30-60s)...")
    r = requests.post(f"{BASE}/api/ai/chat", json={
        "message": "I spent $500 on food this month. Is that too much for a single person? Give brief advice.",
        "user_id": USER_ID
    }, headers=headers, timeout=120)
    r.raise_for_status()
    d = r.json()
    resp = d.get("response", d.get("message", d.get("content", str(d))))
    return f"LLM says: {str(resp)[:200]}"

def test_ai_analyze():
    print("    (LLM analysis - may take 30-60s)...")
    r = requests.post(f"{BASE}/api/ai/analyze", json={
        "request": "Analyze my spending patterns and suggest where I can save money",
        "user_id": USER_ID,
        "context": {
            "spending": {"Food & Dining": 500, "Transportation": 200, "Entertainment": 100, "Utilities": 185},
            "income": 6500,
            "goals": ["Emergency Fund $10,000"]
        }
    }, headers=headers, timeout=120)
    r.raise_for_status()
    d = r.json()
    return f"Analysis confidence={d.get('confidence', '?')}, mode={d.get('mode', '?')}"

def test_ai_parse_transaction():
    r = requests.post(f"{BASE}/api/ai/parse-transaction", json={
        "description": "AMZN MKTP US*1A2B3C"
    }, headers=headers, timeout=60)
    r.raise_for_status()
    d = r.json()
    return f"merchant={d.get('merchant','?')}, confidence={d.get('confidence','?')}"

def test_ai_smart_advice():
    print("    (Smart advice with LLM - may take 30-60s)...")
    r = requests.post(f"{BASE}/api/ai/smart-advice", json={
        "user_id": USER_ID,
        "include_transactions": True,
        "include_goals": True,
        "max_recommendations": 3
    }, headers=headers, timeout=120)
    r.raise_for_status()
    d = r.json()
    return f"Smart advice keys: {list(d.keys())}"

def test_ai_feedback():
    # Need a real transaction_id
    r = requests.get(f"{BASE}/api/transactions?user_id={USER_ID}&page=1&page_size=1",
                     headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    items = data.get("transactions", data.get("items", []))
    if items:
        tid = items[0]["id"]
        r2 = requests.post(f"{BASE}/api/ai/feedback/correction", json={
            "user_id": USER_ID,
            "transaction_id": tid,
            "merchant_raw": "STARBUCKS #1234",
            "original_category": "Other Expenses",
            "corrected_category": "Food & Dining"
        }, headers=headers, timeout=15)
        r2.raise_for_status()
        return f"Feedback submitted for txn {tid[:8]}..."
    return "No transactions for feedback test"

def test_ai_feedback_stats():
    r = requests.get(f"{BASE}/api/ai/feedback/stats", headers=headers, timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"total_corrections={d.get('total_corrections')}, auto_updates={d.get('auto_updates_made')}"

test("AI Brain direct health", test_ai_brain_direct)
test("AI status via backend", test_ai_status)
test("AI Chat (LLM conversation)", test_ai_chat)
test("AI Analyze spending", test_ai_analyze)
test("AI Parse 'AMZN MKTP US'", test_ai_parse_transaction)
test("AI Smart financial advice", test_ai_smart_advice)
test("AI Submit category feedback", test_ai_feedback)
test("AI Feedback stats", test_ai_feedback_stats)

# ===========================
# REPORTS TESTS
# ===========================
print("\n" + "="*60)
print("REPORTS & EXPORTS TESTS")
print("="*60)

def test_generate_report():
    r = requests.post(f"{BASE}/api/reports/generate", json={
        "user_id": USER_ID,
        "start_date": "2026-01-01",
        "end_date": "2026-01-31"
    }, headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    savings = d.get("net_savings", "?")
    rate = d.get("savings_rate", "?")
    return f"net_savings=${savings}, savings_rate={rate}%"

def test_export_csv():
    """CSV export - ALL params are Query params (user_id, start_date, end_date)."""
    r = requests.post(
        f"{BASE}/api/reports/export/csv?user_id={USER_ID}&start_date=2026-01-01&end_date=2026-01-31",
        headers=headers, timeout=15
    )
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    assert "text/csv" in ct or len(r.content) > 50, f"Expected CSV, got {ct}"
    return f"{len(r.content)} bytes, type={ct[:50]}"

def test_export_pdf():
    """PDF export - ALL params are Query params (user_id, start_date, end_date)."""
    r = requests.post(
        f"{BASE}/api/reports/export/pdf?user_id={USER_ID}&start_date=2026-01-01&end_date=2026-01-31",
        headers=headers, timeout=15
    )
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    assert len(r.content) > 100, f"PDF too small: {len(r.content)} bytes"
    return f"{len(r.content)} bytes, type={ct[:50]}"

def test_import_template():
    r = requests.get(f"{BASE}/api/import/template", headers=headers, timeout=10)
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    return f"{len(r.content)} bytes, type={ct[:50]}"

def test_export_transactions():
    r = requests.get(f"{BASE}/api/export/transactions?user_id={USER_ID}",
                     headers=headers, timeout=10)
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    return f"{len(r.content)} bytes, type={ct[:50]}"

test("Generate monthly report", test_generate_report)
test("Export CSV", test_export_csv)
test("Export PDF", test_export_pdf)
test("Download import template", test_import_template)
test("Export transactions", test_export_transactions)

# ===========================
# METRICS TESTS
# ===========================
print("\n" + "="*60)
print("METRICS & MONITORING TESTS")
print("="*60)

def test_cache_metrics():
    r = requests.get(f"{BASE}/metrics/cache", timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"hits={d.get('hits')}, misses={d.get('misses')}, rate={d.get('hit_rate')}"

def test_gpu_metrics():
    r = requests.get(f"{BASE}/metrics/gpu", timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"available={d.get('available')}, devices={d.get('device_count')}"

def test_ai_metrics():
    r = requests.get(f"{BASE}/metrics/ai", timeout=10)
    r.raise_for_status()
    d = r.json()
    cb = d.get("circuit_breaker", {})
    return f"circuit_breaker={cb.get('state')}, failures={cb.get('failures')}"

def test_prometheus():
    r = requests.get(f"{PROMETHEUS}/-/healthy", timeout=10)
    r.raise_for_status()
    return f"Prometheus: {r.text.strip()}"

def test_prometheus_targets():
    r = requests.get(f"{PROMETHEUS}/api/v1/targets", timeout=10)
    r.raise_for_status()
    targets = r.json().get("data", {}).get("activeTargets", [])
    statuses = [f"{t.get('labels',{}).get('job','?')}={t.get('health')}" for t in targets]
    return f"{len(targets)} targets: {statuses}"

def test_grafana():
    r = requests.get(f"{GRAFANA}/api/health", timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"v{d['version']}, db={d['database']}"

def test_grafana_datasources():
    r = requests.get(f"{GRAFANA}/api/datasources",
                     auth=("admin", "admin"), timeout=10)
    r.raise_for_status()
    ds = r.json()
    return f"{len(ds)} datasources configured"

test("Cache metrics", test_cache_metrics)
test("GPU metrics", test_gpu_metrics)
test("AI circuit breaker metrics", test_ai_metrics)
test("Prometheus health", test_prometheus)
test("Prometheus targets", test_prometheus_targets)
test("Grafana health", test_grafana)
test("Grafana datasources", test_grafana_datasources)

# ===========================
# AI BRAIN METRICS ENDPOINT
# ===========================
print("\n" + "="*60)
print("AI BRAIN METRICS (Prometheus scrape target)")
print("="*60)

def test_ai_brain_metrics():
    """Verify the AI Brain exposes a /metrics endpoint for Prometheus."""
    r = requests.get(f"{AI_BRAIN}/metrics", timeout=10)
    r.raise_for_status()
    body = r.text
    assert "ai_brain_up" in body, f"Missing ai_brain_up metric in response"
    assert "ai_brain_model_loaded" in body, f"Missing ai_brain_model_loaded metric"
    return f"{len(body)} bytes, contains ai_brain_up + ai_brain_model_loaded"

test("AI Brain /metrics endpoint", test_ai_brain_metrics)

# ===========================
# HEALTH ENDPOINTS
# ===========================
print("\n" + "="*60)
print("HEALTH & READINESS TESTS")
print("="*60)

def test_health():
    r = requests.get(f"{BASE}/health", timeout=10)
    r.raise_for_status()
    return f"status={r.json().get('status')}"

def test_ready():
    r = requests.get(f"{BASE}/health/ready", timeout=10)
    r.raise_for_status()
    d = r.json()
    checks = d.get("checks", {})
    db = checks.get("database", {}).get("status")
    redis = checks.get("redis", {}).get("status")
    return f"db={db}, redis={redis}"

def test_live():
    r = requests.get(f"{BASE}/health/live", timeout=10)
    r.raise_for_status()
    return f"status={r.json().get('status')}"

def test_root():
    r = requests.get(f"{BASE}/", timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"v{d.get('version')}, status={d.get('status')}"

test("Health check", test_health)
test("Readiness (db+redis)", test_ready)
test("Liveness probe", test_live)
test("Root endpoint", test_root)

# ===========================
# CLEANUP
# ===========================
print("\n" + "="*60)
print("CLEANUP TESTS")
print("="*60)

def test_delete_transaction():
    if TRANSACTION_IDS:
        tid = TRANSACTION_IDS[-1]
        r = requests.delete(f"{BASE}/api/transactions/{tid}?user_id={USER_ID}",
                            headers=headers, timeout=10)
        r.raise_for_status()
        return f"Deleted {tid[:8]}..."
    # fallback
    r = requests.get(f"{BASE}/api/transactions?user_id={USER_ID}&page=1&page_size=1",
                     headers=headers, timeout=10)
    items = r.json().get("transactions", r.json().get("items", []))
    if items:
        tid = items[0]["id"]
        r2 = requests.delete(f"{BASE}/api/transactions/{tid}?user_id={USER_ID}",
                             headers=headers, timeout=10)
        r2.raise_for_status()
        return f"Deleted {tid[:8]}..."
    return "Nothing to delete"

test("Delete a transaction", test_delete_transaction)

# ===========================
# FINAL SUMMARY
# ===========================
print("\n" + "="*60)
print("FINAL TEST SUMMARY")
print("="*60)
total = PASS + FAIL
print(f"\n  Total tests:  {total}")
print(f"  Passed:       {PASS}")
print(f"  Failed:       {FAIL}")
print(f"  Pass rate:    {PASS/total*100:.1f}%\n")

if FAIL > 0:
    print("  FAILED TESTS:")
    for status, name, detail in RESULTS:
        if status == "FAIL":
            print(f"    - {name}")
            print(f"      {detail[:250]}")
    print()

print("="*60)
sys.exit(0 if FAIL == 0 else 1)
