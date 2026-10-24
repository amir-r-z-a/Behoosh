"""ساخت کاربر اولیه و اهداف پیش‌فرض."""
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Goal, User
from app.db.session import SessionLocal


def main() -> None:
    s = get_settings()
    db = SessionLocal()
    try:
        u = db.execute(select(User)).scalars().first()
        if not u:
            u = User(display_name="امیرمهدی", method="hybrid", timezone=s.timezone)
            db.add(u)
            db.flush()
            print("created user", u.id)
        for gt, val, unit in (
            ("kcal", s.default_kcal_target, "kcal"),
            ("protein", s.default_protein_target, "g"),
            ("sleep", s.default_sleep_target, "h"),
            ("screen_total", s.default_screen_target_min, "min"),
            ("screen_instagram", s.default_instagram_target_min, "min"),
        ):
            if not db.execute(select(Goal).where(Goal.user_id == u.id,
                                                 Goal.goal_type == gt)).scalars().first():
                db.add(Goal(user_id=u.id, goal_type=gt, target_value=val, target_unit=unit))
        db.commit()
        print("seed done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
