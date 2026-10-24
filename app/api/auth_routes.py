"""مسیرهای احراز هویت: ثبت‌نام، ورود، پروفایل، ساخت و ابطال توکن.

فاز اول: ایمیل و پسورد ساده، بدون تایید ایمیل. عمدا ساده نگه داشته شده.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import ALL_SCOPES, Principal, get_principal, require_scope
from app.core.security import hash_password, new_token, verify_password, hash_token
from app.db.auth_models import ApiToken, AuthCredential
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenIn(BaseModel):
    name: str = Field(default="", max_length=120)
    scopes: list[str] = Field(default_factory=list)
    kind: str = "api"


class TokenOut(BaseModel):
    id: str
    name: str
    scopes: list[str]
    kind: str
    token: str | None = None  # فقط در لحظه ساخت برمی‌گردد


@router.post("/register", status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """ساخت کاربر + اعتبارنامه. بدون تایید ایمیل در این فاز."""
    email = payload.email.lower().strip()
    exists = db.execute(
        select(AuthCredential).where(func.lower(AuthCredential.email) == email)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    user = User(display_name=payload.display_name)
    db.add(user)
    db.flush()
    db.add(AuthCredential(user_id=user.id, email=email,
                          password_hash=hash_password(payload.password)))
    db.flush()
    # دسته‌های پیش‌فرض فارسی از روز اول، تا کاربر مجبور نباشد دستی بسازد.
    try:
        from app.services.finance import ensure_default_categories
        ensure_default_categories(db, user.id, commit=False)
    except Exception:
        pass  # اگر اسکیمای مالی بالا نبود، ثبت‌نام نباید بشکند
    db.commit()
    return {"ok": True, "user_id": str(user.id), "email": email}


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """ورود. یک توکن دسترسی برمی‌گرداند که خودش هویت است."""
    email = payload.email.lower().strip()
    cred = db.execute(
        select(AuthCredential).where(func.lower(AuthCredential.email) == email)
    ).scalar_one_or_none()
    if cred is None or not cred.active or not verify_password(payload.password, cred.password_hash):
        # پیام یکسان برای هر دو حالت: جلوگیری از افشای وجود ایمیل
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")

    raw = new_token()
    row = ApiToken(user_id=cred.user_id, token_hash=hash_token(raw),
                   scopes=list(ALL_SCOPES), name="login", kind="session")
    db.add(row)
    cred.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "token": raw, "scopes": list(ALL_SCOPES),
            "user_id": str(cred.user_id)}


@router.get("/me")
def me(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """پروفایل کاربر جاری. user_id از توکن می‌آید."""
    user = db.get(User, p.user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    return {
        "user_id": str(user.id),
        "display_name": user.display_name,
        "timezone": user.timezone,
        "language": user.language,
        "method": user.method,
        "scopes": sorted(p.scopes),
        "token_kind": p.kind,
    }


@router.post("/tokens", status_code=201)
def create_token(payload: TokenIn, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)):
    """ساخت توکن جدید برای ایجنت. توکن خام فقط همین یک بار برمی‌گردد."""
    scopes = payload.scopes or list(ALL_SCOPES)
    unknown = set(scopes) - set(ALL_SCOPES)
    if unknown:
        raise HTTPException(400, f"unknown scopes: {sorted(unknown)}")
    # کاربر نمی‌تواند scope بیشتر از خودش بسازد
    if not p.has("*") and not set(scopes) <= p.scopes:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot grant scopes you lack")

    raw = new_token()
    row = ApiToken(user_id=p.user_id, token_hash=hash_token(raw),
                   scopes=scopes, name=payload.name, kind=payload.kind)
    db.add(row)
    db.commit()
    return TokenOut(id=str(row.id), name=row.name, scopes=scopes,
                    kind=row.kind, token=raw)


@router.get("/tokens")
def list_tokens(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """لیست توکن‌های من. توکن خام هرگز برنمی‌گردد."""
    rows = db.execute(
        select(ApiToken).where(ApiToken.user_id == p.user_id,
                               ApiToken.revoked.is_(False))
        .order_by(ApiToken.created_at.desc())
    ).scalars().all()
    return {"tokens": [
        {"id": str(r.id), "name": r.name, "scopes": r.scopes, "kind": r.kind,
         "created_at": r.created_at, "last_used_at": r.last_used_at}
        for r in rows
    ]}


@router.delete("/tokens/{token_id}")
def revoke_token(token_id: str, p: Principal = Depends(get_principal),
                 db: Session = Depends(get_db)):
    """ابطال توکن. حذف نمی‌کند، فقط revoked می‌کند تا ردپا بماند."""
    row = db.execute(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == p.user_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "token not found")
    row.revoked = True
    db.commit()
    return {"ok": True, "revoked": str(row.id)}
