"""سرور MCP بهوش (streamable-http). تول‌ها آینه API هستند."""
import json
import os
from datetime import date

import httpx
from mcp.server.fastmcp import FastMCP

from app.mcp import _auth, live_tools

API = os.getenv("BEHOOSH_API", "http://api:8000")
# توکن از هدر درخواست کاربر خوانده می‌شود (app/mcp/_auth.py).
# توکن محیطی فقط به‌عنوان fallback اختیاری است.
_auth.set_env_token(os.getenv("API_TOKEN", ""))

mcp = FastMCP("behoosh", host="0.0.0.0", port=8001)


def _post(path: str, body: dict) -> dict:
    r = httpx.post(f"{API}/v1{path}", json=body,
                   headers={"X-API-Key": _auth.current_token()}, timeout=30)
    r.raise_for_status()
    return r.json()


def _get(path: str, params: dict) -> dict:
    r = httpx.get(f"{API}/v1{path}", params=params,
                  headers={"X-API-Key": _auth.current_token()}, timeout=30)
    r.raise_for_status()
    return r.json()


def _patch(path: str, body: dict) -> dict:
    r = httpx.patch(f"{API}/v1{path}", json=body,
                    headers={"X-API-Key": _auth.current_token()}, timeout=30)
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> dict:
    r = httpx.delete(f"{API}/v1{path}", headers={"X-API-Key": _auth.current_token()}, timeout=30)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def log_meal(log_date: str, slot: str, items: list[dict]) -> str:
    """ثبت وعده غذایی. slot: breakfast|snack|lunch|evening|dinner|after_dinner.
    هر آیتم: name, quantity, unit(gram|spoon|piece|glass|palm|bowl), kcal, protein_g,
    carbs_g, fat_g, و اختیاری cold_warm/dry_wet (مزاج قلم، بازه -1..1).
    cold_warm: منفی=سرد مثبت=گرم؛ dry_wet: منفی=تر مثبت=خشک."""
    return json.dumps(_post("/log_meal", {"log_date": log_date, "slot": slot, "items": items}),
                      ensure_ascii=False)


@mcp.tool()
def list_meals(log_date: str) -> str:
    """لیست ردیف‌های غذای یک روز با شناسه (برای ویرایش/حذف)."""
    return json.dumps(_get("/meals", {"d": log_date}), ensure_ascii=False)


@mcp.tool()
def update_meal(meal_id: str, slot: str | None = None, item_name: str | None = None,
                quantity: float | None = None, unit: str | None = None,
                kcal: float | None = None, protein_g: float | None = None,
                carbs_g: float | None = None, fat_g: float | None = None,
                cold_warm: float | None = None, dry_wet: float | None = None) -> str:
    """ویرایش یک ردیف غذا با شناسه. فقط فیلدهای داده‌شده تغییر می‌کنند."""
    body = {k: v for k, v in {
        "slot": slot, "item_name": item_name, "quantity": quantity, "unit": unit,
        "kcal": kcal, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g,
        "cold_warm": cold_warm, "dry_wet": dry_wet}.items() if v is not None}
    return json.dumps(_patch(f"/meals/{meal_id}", body), ensure_ascii=False)


@mcp.tool()
def delete_meal(meal_id: str) -> str:
    """حذف یک ردیف غذا با شناسه."""
    return json.dumps(_delete(f"/meals/{meal_id}"), ensure_ascii=False)


@mcp.tool()
def log_sleep(log_date: str, main_hours: float, quality: int = 0,
              nap_min: int = 0, wake_count: int = 0, bedtime: str | None = None,
              wake_time: str | None = None, note: str | None = None) -> str:
    """ثبت خواب. main_hours اعشاری مثل 7.5.
    bedtime/wake_time هم 'HH:MM' (مثل 23:30) و هم ISO کامل پذیرفته می‌شود."""
    body = {"log_date": log_date, "main_hours": main_hours, "quality": quality,
            "nap_min": nap_min, "wake_count": wake_count, "note": note}
    if bedtime:
        body["bedtime"] = bedtime
    if wake_time:
        body["wake_time"] = wake_time
    return json.dumps(_post("/log_sleep", body), ensure_ascii=False)


@mcp.tool()
def log_workout(log_date: str, kind: str, duration_min: int,
                kcal_burned: float = 0, muscles: list[str] | None = None,
                sets: list[dict] | None = None, notes: str | None = None) -> str:
    """ثبت ورزش. sets: exercise, muscle_group, sets, reps, weight_kg."""
    return json.dumps(_post("/log_workout", {
        "log_date": log_date, "kind": kind, "duration_min": duration_min,
        "kcal_burned": kcal_burned, "muscles": muscles or [],
        "sets": sets or [], "notes": notes}), ensure_ascii=False)


@mcp.tool()
def log_body(measured_at: str, weight_kg: float = 0, body_fat_pct: float = 0,
             visceral_fat: float = 0, muscle_kg: float = 0, muscle_pct: float = 0,
             water_pct: float = 0, bmi: float = 0) -> str:
    """ثبت اندازه‌گیری بدن از ترازو بدن‌سنج."""
    return json.dumps(_post("/log_body", {
        "measured_at": measured_at, "weight_kg": weight_kg, "body_fat_pct": body_fat_pct,
        "visceral_fat": visceral_fat, "muscle_kg": muscle_kg, "muscle_pct": muscle_pct,
        "water_pct": water_pct, "bmi": bmi}), ensure_ascii=False)


@mcp.tool()
def log_prayer(log_date: str, prayer: str, status: str) -> str:
    """ثبت نماز. prayer: fajr|dhuhr|asr|maghrib|isha. status: done|late|qada|missed."""
    return json.dumps(_post("/log_prayer", {"log_date": log_date, "prayer": prayer,
                                            "status": status}), ensure_ascii=False)


@mcp.tool()
def log_mood(log_date: str, mood: int = 0, stress: int = 0, energy: int = 0,
             note: str | None = None) -> str:
    """ثبت حال و احساس. هر شاخص ۰ تا ۱۰."""
    return json.dumps(_post("/log_mood", {"log_date": log_date, "mood": mood,
                                          "stress": stress, "energy": energy,
                                          "note": note}), ensure_ascii=False)


@mcp.tool()
def log_screen_time(log_date: str, total_min: int, instagram_min: int = 0,
                    telegram_min: int = 0, unlocks: int = 0,
                    notifications: int = 0) -> str:
    """ثبت اسکرین‌تایم روزانه به دقیقه."""
    other = max(total_min - instagram_min - telegram_min, 0)
    return json.dumps(_post("/log_screen_time", {
        "log_date": log_date, "total_min": total_min, "instagram_min": instagram_min,
        "telegram_min": telegram_min, "other_min": other,
        "unlocks": unlocks, "notifications": notifications}), ensure_ascii=False)


@mcp.tool()
def log_habit(log_date: str, breathing_done: bool = False, water_liters: float = 0,
              supplements: list[str] | None = None, teas: list[str] | None = None) -> str:
    """ثبت عادت‌ها: تنفس عمیق، آب، مکمل، دمنوش."""
    return json.dumps(_post("/log_habit", {
        "log_date": log_date, "breathing_done": breathing_done,
        "water_liters": water_liters, "supplements": supplements or [],
        "teas": teas or []}), ensure_ascii=False)


@mcp.tool()
def get_day_summary(log_date: str | None = None) -> str:
    """جمع روز: کالری، پروتئین، خواب، ورزش، نماز، حال، اسکرین‌تایم، مزاج دو محوره و باقی‌مانده تا هدف."""
    d = log_date or date.today().isoformat()
    return json.dumps(_get("/day_summary", {"d": d}), ensure_ascii=False)


@mcp.tool()
def get_trends(metric: str, days: int = 14) -> str:
    """روند یک شاخص. metric: kcal|meals|protein|weight|sleep|temperament."""
    return json.dumps(_get("/trends", {"metric": metric, "days": days}), ensure_ascii=False)


@mcp.tool()
def get_temperament_state(log_date: str | None = None) -> str:
    """نقطه مزاج کنونی: بردار پایه + بردار امروز + حالت تجمعی."""
    d = log_date or date.today().isoformat()
    return json.dumps(_get("/temperament_state", {"d": d}), ensure_ascii=False)


@mcp.tool()
def get_temperament_profile() -> str:
    """مزاج پایه کاربر (نقطه لنگر صفحه دو محوره)."""
    return json.dumps(_get("/temperament_profile", {}), ensure_ascii=False)


@mcp.tool()
def set_temperament_profile(base_cold_warm: float, base_dry_wet: float,
                            constitution: str | None = None,
                            method: str = "hybrid", note: str | None = None) -> str:
    """ثبت مزاج پایه از پرسشنامه و معاینه. بازه هر محور -1..1.
    constitution: سوداوی|صفراوی|دموی|بلغمی|مرکب."""
    return json.dumps(_post("/temperament_profile", {
        "base_cold_warm": base_cold_warm, "base_dry_wet": base_dry_wet,
        "constitution": constitution, "method": method, "note": note}),
        ensure_ascii=False)


@mcp.tool()
def log_temperament_exam(organ: str, cold_warm: float, dry_wet: float,
                         measured_at: str, severity: int = 0,
                         finding: str | None = None) -> str:
    """ثبت بردار مزاج یک عضو از معاینه. organ: heart|liver|stomach|brain|kidney|lung|...
    بازه هر محور -1..1؛ severity درجه ۰ تا ۳."""
    return json.dumps(_post("/log_temperament_exam", {
        "organ": organ, "cold_warm": cold_warm, "dry_wet": dry_wet,
        "severity": severity, "finding": finding, "measured_at": measured_at}),
        ensure_ascii=False)


@mcp.tool()
def get_temperament_exam() -> str:
    """لیست معاینه ارگان‌ها + میانگین بردار (مبنای مزاج پایه)."""
    return json.dumps(_get("/temperament_exam", {}), ensure_ascii=False)


@mcp.tool()
def get_temperament_vectors(item_type: str | None = None, q: str | None = None) -> str:
    """لیست بردارهای پایه اقلام. item_type: food|behavior|intervention."""
    params = {}
    if item_type:
        params["item_type"] = item_type
    if q:
        params["q"] = q
    return json.dumps(_get("/temperament_vectors", params), ensure_ascii=False)


@mcp.tool()
def log_temperament_vector(item_name: str, cold_warm: float, dry_wet: float,
                           item_type: str = "food", source_ref: str | None = None) -> str:
    """ثبت/ویرایش بردار پایه یک قلم. اگر source_ref بدهی، verified می‌شود."""
    return json.dumps(_post("/log_temperament_vector", {
        "item_name": item_name, "item_type": item_type,
        "cold_warm": cold_warm, "dry_wet": dry_wet,
        "source_ref": source_ref}), ensure_ascii=False)


@mcp.tool()
def get_targets() -> str:
    """اهداف فعال کاربر."""
    return json.dumps(_get("/targets", {}), ensure_ascii=False)


live_tools.register(mcp)


if __name__ == "__main__":
    _auth.serve(mcp, 8001)
