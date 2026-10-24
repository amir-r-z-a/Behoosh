"""خواندن تجمیعی سلامت: جمع روز، روند شاخص‌ها، اهداف."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_deps import Principal
from app.api.health._common import HEALTH_READ, _uid
from app.api.summary import day_summary
from app.core.config import get_settings
from app.db.models import BodyMetric, Meal, SleepLog
from app.db.session import get_db

router = APIRouter()


@router.get("/day_summary")
def get_day_summary(d: date | None = None,
                    date_q: date | None = Query(None, alias="date"),
                    db: Session = Depends(get_db),
                    p: Principal = Depends(HEALTH_READ)):
    """جمع روز. هم پارامتر d و هم date پذیرفته می‌شود. احراز هویت توکنی."""
    return day_summary(db, _uid(p), d or date_q or date.today())


@router.get("/trends")
def get_trends(metric: str, days: int = 14, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_READ)):
    uid = _uid(p)
    start = date.today() - timedelta(days=days - 1)
    if metric in ("kcal", "meals"):
        rows = db.execute(
            select(Meal.log_date, Meal.kcal).where(
                Meal.user_id == uid, Meal.log_date >= start)).all()
        agg: dict = {}
        for d_, k in rows:
            agg[d_] = agg.get(d_, 0) + float(k)
        return {"metric": metric, "points": [{"d": k, "v": v} for k, v in sorted(agg.items())]}
    if metric == "weight":
        rows = db.execute(
            select(BodyMetric.measured_at, BodyMetric.weight_kg).where(
                BodyMetric.user_id == uid, BodyMetric.measured_at >= start)
            .order_by(BodyMetric.measured_at)).all()
        return {"metric": metric, "points": [{"d": d_, "v": float(w)} for d_, w in rows]}
    if metric == "sleep":
        rows = db.execute(
            select(SleepLog.log_date, SleepLog.main_hours).where(
                SleepLog.user_id == uid, SleepLog.log_date >= start)
            .order_by(SleepLog.log_date)).all()
        return {"metric": metric, "points": [{"d": d_, "v": float(h)} for d_, h in rows]}
    if metric == "protein":
        rows = db.execute(
            select(Meal.log_date, Meal.protein_g).where(
                Meal.user_id == uid, Meal.log_date >= start)).all()
        agg = {}
        for d_, p in rows:
            agg[d_] = agg.get(d_, 0) + float(p)
        return {"metric": metric, "points": [{"d": k, "v": v} for k, v in sorted(agg.items())]}
    if metric == "temperament":
        from app.db.models import TemperamentState
        rows = db.execute(
            select(TemperamentState.log_date, TemperamentState.cold_warm,
                   TemperamentState.dry_wet).where(
                TemperamentState.user_id == uid, TemperamentState.log_date >= start)
            .order_by(TemperamentState.log_date)).all()
        return {"metric": metric, "points": [
            {"d": d_, "cw": float(cw), "dw": float(dw)} for d_, cw, dw in rows]}
    raise HTTPException(400, f"unknown metric: {metric}")


@router.get("/targets")
def get_targets(db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_READ)):
    s = get_settings()
    return {
        "kcal": s.default_kcal_target,
        "protein_g": s.default_protein_target,
        "sleep_hours": s.default_sleep_target,
        "screen_total_min": s.default_screen_target_min,
        "screen_instagram_min": s.default_instagram_target_min,
    }

