"""ساخت یا تغییر اعتبارنامه ورود برای کاربر موجود.

کاربرد:
    python -m app.db.set_password --email me@example.com --password 'secret123'
    python -m app.db.set_password --email me@example.com --password 'secret123' --name 'امیرمهدی'

اگر کاربری وجود نداشته باشد ساخته می‌شود. اگر ایمیل قبلا باشد رمزش عوض می‌شود.
رمز هرگز در لاگ چاپ نمی‌شود.
"""
import argparse
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.auth_models import AuthCredential
from app.db.models import User
from app.db.session import SessionLocal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--name", default=None, help="نام نمایشی، فقط وقتی کاربر ساخته می‌شود")
    args = ap.parse_args()

    email = args.email.lower().strip()
    if len(args.password) < 8:
        print("رمز باید حداقل ۸ کاراکتر باشد", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        cred = db.execute(
            select(AuthCredential).where(func.lower(AuthCredential.email) == email)
        ).scalar_one_or_none()

        if cred is not None:
            cred.password_hash = hash_password(args.password)
            cred.active = True
            db.commit()
            print("updated credential for %s (user %s)" % (email, cred.user_id))
            return 0

        # کاربر موجود را بردار، وگرنه بساز
        user = db.execute(select(User).order_by(User.created_at)).scalars().first()
        if user is None:
            user = User(display_name=args.name or "کاربر")
            db.add(user)
            db.flush()

        db.add(AuthCredential(user_id=user.id, email=email,
                              password_hash=hash_password(args.password)))
        db.commit()
        print("created credential for %s (user %s)" % (email, user.id))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
