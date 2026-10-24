"""مزاج دو محوره: مزاج پایه، معاینه ارگان‌ها، بردارهای پایه اقلام، حالت روز."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as S
from app.api.auth_deps import Principal
from app.api.health._common import HEALTH_READ, HEALTH_WRITE, _uid
from app.db.models import (
    TemperamentExam, TemperamentProfile, TemperamentVector,
)
from app.db.session import get_db

router = APIRouter()


@router.post("/temperament_profile")
def set_temperament_profile(payload: S.TemperamentProfileIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    """ثبت/به‌روزرسانی مزاج پایه کاربر (نقطه لنگر صفحه دو محوره)."""
    uid = _uid(p)
    row = db.execute(select(TemperamentProfile).where(
        TemperamentProfile.user_id == uid)).scalar_one_or_none()
    if row is None:
        row = TemperamentProfile(user_id=uid)
        db.add(row)
    row.base_cold_warm = payload.base_cold_warm
    row.base_dry_wet = payload.base_dry_wet
    row.constitution = payload.constitution
    row.method = payload.method
    row.note = payload.note
    db.commit()
    return {"ok": True, "base_cold_warm": float(row.base_cold_warm),
            "base_dry_wet": float(row.base_dry_wet),
            "constitution": row.constitution, "method": row.method}


@router.get("/temperament_profile")
def get_temperament_profile(db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_READ)):
    """مزاج پایه کاربر. اگر ثبت نشده، پیش‌فرض صفر."""
    uid = _uid(p)
    row = db.execute(select(TemperamentProfile).where(
        TemperamentProfile.user_id == uid)).scalar_one_or_none()
    if row is None:
        return {"base_cold_warm": 0, "base_dry_wet": 0,
                "constitution": None, "method": "hybrid", "set": False}
    return {"base_cold_warm": float(row.base_cold_warm),
            "base_dry_wet": float(row.base_dry_wet),
            "constitution": row.constitution, "method": row.method, "set": True}


@router.post("/log_temperament_exam")
def log_temperament_exam(payload: S.TemperamentExamIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    """ثبت بردار مزاج یک عضو از معاینه. کلید یکتا: (user_id, organ)."""
    uid = _uid(p)
    row = db.execute(select(TemperamentExam).where(
        TemperamentExam.user_id == uid,
        TemperamentExam.organ == payload.organ)).scalar_one_or_none()
    if row is None:
        row = TemperamentExam(user_id=uid, organ=payload.organ)
        db.add(row)
    row.cold_warm = payload.cold_warm
    row.dry_wet = payload.dry_wet
    row.severity = payload.severity
    row.finding = payload.finding
    row.source = payload.source
    row.measured_at = payload.measured_at
    db.commit()
    return {"ok": True, "organ": payload.organ,
            "cold_warm": payload.cold_warm, "dry_wet": payload.dry_wet,
            "severity": payload.severity}


@router.get("/temperament_exam")
def get_temperament_exam(db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_READ)):
    """لیست معاینه ارگان‌ها + میانگین بردار (مبنای مزاج پایه)."""
    uid = _uid(p)
    rows = db.execute(select(TemperamentExam).where(
        TemperamentExam.user_id == uid).order_by(TemperamentExam.organ)).scalars().all()
    if not rows:
        return {"count": 0, "organs": [], "avg_cold_warm": 0, "avg_dry_wet": 0}
    cw = sum(float(r.cold_warm) for r in rows) / len(rows)
    dw = sum(float(r.dry_wet) for r in rows) / len(rows)
    return {
        "count": len(rows),
        "organs": [{"organ": r.organ, "cold_warm": float(r.cold_warm),
                     "dry_wet": float(r.dry_wet), "severity": r.severity,
                     "finding": r.finding, "measured_at": r.measured_at}
                    for r in rows],
        "avg_cold_warm": round(cw, 3), "avg_dry_wet": round(dw, 3),
    }


@router.post("/log_temperament_vector")
def log_temperament_vector(payload: S.TemperamentVectorIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    """ثبت/ویرایش بردار پایه یک قلم (غذا/رفتار/مداخله). جدول مرجع مشترک است، نه کاربری."""
    row = db.execute(select(TemperamentVector).where(
        TemperamentVector.item_name == payload.item_name,
        TemperamentVector.item_type == payload.item_type)).scalar_one_or_none()
    if row is None:
        row = TemperamentVector(item_name=payload.item_name, item_type=payload.item_type)
        db.add(row)
    row.cold_warm = payload.cold_warm
    row.dry_wet = payload.dry_wet
    row.source_ref = payload.source_ref
    row.verified = bool(payload.source_ref)
    db.commit()
    return {"ok": True, "item_name": payload.item_name,
            "cold_warm": payload.cold_warm, "dry_wet": payload.dry_wet,
            "verified": row.verified}


@router.get("/temperament_vectors", dependencies=[Depends(HEALTH_READ)])
def list_temperament_vectors(item_type: str | None = None, q: str | None = None,
                             db: Session = Depends(get_db)):
    """لیست بردارهای پایه، با فیلتر نوع و جستجوی نام."""
    stmt = select(TemperamentVector)
    if item_type:
        stmt = stmt.where(TemperamentVector.item_type == item_type)
    if q:
        stmt = stmt.where(TemperamentVector.item_name.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(TemperamentVector.item_name)).scalars().all()
    return {"count": len(rows), "items": [
        {"item_name": r.item_name, "item_type": r.item_type,
         "cold_warm": float(r.cold_warm), "dry_wet": float(r.dry_wet),
         "verified": r.verified, "source_ref": r.source_ref} for r in rows]}


@router.get("/temperament_state")
def get_temperament_state(d: date | None = None, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_READ)):
    """نقطه مزاج کنونی: بردار پایه + بردار امروز."""
    from app.temperament import day_vector, label, state_vector
    uid = _uid(p)
    target = d or date.today()
    prof = db.execute(select(TemperamentProfile).where(
        TemperamentProfile.user_id == uid)).scalar_one_or_none()
    base = {"cold_warm": float(prof.base_cold_warm) if prof else 0,
            "dry_wet": float(prof.base_dry_wet) if prof else 0}
    dcw, ddw, n = day_vector(db, uid, target)
    scw, sdw = state_vector(db, uid, target)
    return {"log_date": target, "base": base,
            "today": {"cold_warm": round(dcw, 3), "dry_wet": round(ddw, 3),
                       "label": label(dcw, ddw) if n else "بدون داده", "items": n},
            "state": {"cold_warm": round(scw, 3), "dry_wet": round(sdw, 3),
                       "label": label(scw, sdw)}}
