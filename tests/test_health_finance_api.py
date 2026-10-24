"""مسیرهای اصلی سلامت و مالی، از ثبت تا خواندن."""

D = "2026-10-20"


def test_meal_flow_updates_day_summary(client, user):
    h = user["headers"]
    r = client.post("/v1/log_meal", headers=h, json={
        "log_date": D, "slot": "lunch", "items": [
            {"name": "مرغ", "quantity": 150, "unit": "gram", "kcal": 300, "protein_g": 40},
            {"name": "برنج", "quantity": 200, "unit": "gram", "kcal": 260, "protein_g": 5},
        ]})
    assert r.status_code == 200
    s = r.json()
    assert s["kcal"] == 560 and s["protein_g"] == 45

    items = client.get("/v1/meals", params={"d": D}, headers=h).json()["items"]
    rice = next(i for i in items if i["item_name"] == "برنج")
    assert client.patch(f"/v1/meals/{rice['id']}", headers=h,
                        json={"kcal": 200}).status_code == 200
    chicken = next(i for i in items if i["item_name"] == "مرغ")
    assert client.delete(f"/v1/meals/{chicken['id']}", headers=h).status_code == 200

    s = client.get("/v1/day_summary", params={"date": D}, headers=h).json()
    assert s["kcal"] == 200


def test_sleep_accepts_hh_mm_and_rejects_garbage(client, user):
    h = user["headers"]
    r = client.post("/v1/log_sleep", headers=h, json={
        "log_date": D, "main_hours": 7.5, "quality": 8,
        "bedtime": "23:30", "wake_time": "07:00"})
    assert r.status_code == 200
    assert r.json()["sleep_hours"] == 7.5
    r = client.post("/v1/log_sleep", headers=h, json={
        "log_date": D, "main_hours": 7, "bedtime": "late"})
    assert r.status_code == 422


def test_daily_logs_upsert(client, user):
    h = user["headers"]
    for body, path in (
        ({"log_date": D, "prayer": "fajr", "status": "done"}, "/v1/log_prayer"),
        ({"log_date": D, "mood": 6, "stress": 3, "energy": 7}, "/v1/log_mood"),
        ({"log_date": D, "mood": 8, "stress": 2, "energy": 7}, "/v1/log_mood"),
        ({"log_date": D, "total_min": 300, "instagram_min": 60}, "/v1/log_screen_time"),
        ({"log_date": D, "water_liters": 2.5, "breathing_done": True}, "/v1/log_habit"),
        ({"log_date": D, "kind": "gym", "duration_min": 45,
          "sets": [{"exercise": "squat", "sets": 3, "reps": 8, "weight_kg": 60}]},
         "/v1/log_workout"),
    ):
        assert client.post(path, headers=h, json=body).status_code == 200, path
    s = client.get("/v1/day_summary", params={"d": D}, headers=h).json()
    assert s["prayers_done"] == 1
    assert s["mood"] == 8
    assert s["workout_min"] == 45
    assert s["water_liters"] == 2.5


def test_trends_and_dashboard(client, user):
    h = user["headers"]
    client.post("/v1/log_body", headers=h, json={"measured_at": D, "weight_kg": 80})
    pts = client.get("/v1/trends", params={"metric": "weight", "days": 3650},
                     headers=h).json()["points"]
    assert pts and pts[-1]["v"] == 80
    assert client.get("/v1/trends", params={"metric": "nope"}, headers=h).status_code == 400
    dash = client.get("/v1/dashboard", params={"days": 7}, headers=h).json()
    assert len(dash["days"]) == 7
    assert dash["body"][0]["weight_kg"] == 80


def test_temperament_profile(client, user):
    h = user["headers"]
    assert client.get("/v1/temperament_profile", headers=h).json()["set"] is False
    client.post("/v1/temperament_profile", headers=h,
                json={"base_cold_warm": 0.3, "base_dry_wet": -0.2})
    prof = client.get("/v1/temperament_profile", headers=h).json()
    assert prof["set"] and prof["base_cold_warm"] == 0.3
    vecs = client.get("/v1/temperament_vectors", params={"q": "خرما"}, headers=h).json()
    assert vecs["count"] == 1


def test_finance_double_entry_flow(client, user):
    h = user["headers"]
    r = client.post("/v1/finance/account", headers=h,
                    json={"name": "ملت", "type": "بانک", "card_last4": "1234"})
    assert r.status_code == 201, r.text
    acc = next(a for a in client.get("/v1/finance/accounts", headers=h).json()["accounts"]
               if a["name"] == "ملت")
    assert acc["type"] == "asset"

    r = client.post("/v1/finance/transaction", headers=h, json={
        "occurred_at": "1405/07/25", "amount": 100000, "direction": "credit",
        "account_id": acc["id"], "description": "حقوق"})
    assert r.status_code == 201, r.text

    # پیامک: حساب از چهار رقم آخر کارت پیدا می‌شود؛ ثبت دوباره همان پیگیری تکراری نمی‌شود
    sms = "برداشت مبلغ 250,000 ریال از کارت ****1234 شماره پیگیری: 555111"
    assert client.post("/v1/finance/sms", headers=h, json={"body": sms}).status_code == 201
    client.post("/v1/finance/sms", headers=h, json={"body": sms})

    bal = {b["id"]: b["balance"] for b in
           client.get("/v1/finance/balance", headers=h).json()["balances"]}
    assert bal[acc["id"]] == 100000 - 25000

    assert client.post("/v1/finance/account", headers=h,
                       json={"name": "x", "type": "nonsense"}).status_code == 422


def _accounts(client, h):
    client.post("/v1/finance/account", headers=h, json={"name": "بانک", "type": "بانک"})
    client.post("/v1/finance/account", headers=h, json={"name": "نقد", "type": "نقد"})
    return {a["name"]: a["id"] for a in
            client.get("/v1/finance/accounts", headers=h).json()["accounts"]}


def test_transaction_list_reports_users_point_of_view(client, user):
    h = user["headers"]
    acc = _accounts(client, h)
    for body in (
        {"amount": 500, "direction": "debit", "description": "خرید"},
        {"amount": 9000, "direction": "credit", "description": "حقوق"},
        {"amount": 200, "direction": "debit", "description": "انتقال",
         "counter_account_id": acc["نقد"], "is_transfer": True},
    ):
        r = client.post("/v1/finance/transaction", headers=h,
                        json={"occurred_at": "2026-10-20", "account_id": acc["بانک"], **body})
        assert r.status_code == 201, r.text

    txs = {t["description"]: t for t in client.get(
        "/v1/finance/transactions", params={"start": "2026-10-01", "end": "2026-10-31"},
        headers=h).json()["transactions"]}
    assert (txs["خرید"]["direction"], txs["خرید"]["kind"]) == ("debit", "expense")
    assert (txs["حقوق"]["direction"], txs["حقوق"]["kind"]) == ("credit", "income")
    t = txs["انتقال"]
    assert (t["direction"], t["kind"], t["account"], t["counter_account"]) == (
        "debit", "transfer", "بانک", "نقد")
    assert txs["خرید"]["account"] == "بانک" and txs["خرید"]["amount"] == 500

    out = client.get("/v1/finance/transactions", headers=h, params={
        "start": "2026-10-01", "end": "2026-10-31", "direction": "credit"}).json()
    assert [x["description"] for x in out["transactions"]] == ["حقوق"]
    cash = client.get("/v1/finance/transactions", headers=h, params={
        "start": "2026-10-01", "end": "2026-10-31", "account_id": acc["نقد"]}).json()
    assert [x["description"] for x in cash["transactions"]] == ["انتقال"]


def test_cashflow_by_jalali_month(client, user):
    h = user["headers"]
    acc = _accounts(client, h)
    for d, amt, direction in (("1405/07/10", 1000, "credit"), ("1405/07/12", 300, "debit"),
                              ("1405/06/05", 50, "debit")):
        client.post("/v1/finance/transaction", headers=h, json={
            "occurred_at": d, "amount": amt, "direction": direction, "account_id": acc["بانک"]})
    from datetime import date

    from app.db.session import SessionLocal
    from app.services import finance as svc

    db = SessionLocal()
    try:
        uid = user["user_id"]
        months = svc.cashflow(db, uid, 3, today=date(2026, 10, 20))
    finally:
        db.close()
    assert [m["month"] for m in months] == ["1405/05", "1405/06", "1405/07"]
    assert months[-1]["income"] == 1000 and months[-1]["expense"] == 300
    assert months[1]["expense"] == 50
    r = client.get("/v1/finance/cashflow", params={"months": 2}, headers=h)
    assert r.status_code == 200 and len(r.json()["months"]) == 2


def test_dashboard_details(client, user):
    from datetime import date
    h = user["headers"]
    today = date.today().isoformat()
    client.post("/v1/log_meal", headers=h, json={"log_date": today, "slot": "lunch", "items": [
        {"name": "مرغ", "quantity": 150, "unit": "gram", "kcal": 300, "protein_g": 40}]})
    client.post("/v1/log_sleep", headers=h, json={
        "log_date": today, "main_hours": 7, "bedtime": "23:30", "wake_time": "06:30"})
    client.post("/v1/log_workout", headers=h, json={
        "log_date": today, "kind": "باشگاه", "duration_min": 40, "muscles": ["chest"],
        "sets": [{"exercise": "پرس", "sets": 4, "reps": 10, "weight_kg": 50}]})
    client.post("/v1/log_prayer", headers=h, json={"log_date": today, "prayer": "fajr",
                                                   "status": "done"})
    d = client.get("/v1/dashboard", params={"days": 7}, headers=h).json()
    assert d["meals_today"][0]["name"] == "مرغ"
    assert d["sleep_log"][0]["bedtime"] == "23:30"
    assert d["workouts"][0]["sets"][0]["exercise"] == "پرس"
    assert d["prayers_today"] == {"fajr": "done"}
    assert d["habit_today"] is None
    assert client.get("/v1/dashboard", params={"days": 999}, headers=h).status_code == 422
