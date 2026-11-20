import os

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import AppUser


def main() -> None:
    email = os.environ["BOOTSTRAP_ADMIN_EMAIL"].strip().lower()
    password = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]
    full_name = os.getenv("BOOTSTRAP_ADMIN_FULL_NAME", "").strip() or None

    db = SessionLocal()

    try:
        user_count = db.scalar(
            select(func.count()).select_from(AppUser)
        )

        if user_count != 0:
            raise RuntimeError(
                "Bootstrap refused: app_user already contains users"
            )

        admin = AppUser(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role="ADMIN",
            is_active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"Initial ADMIN created successfully: {admin.email}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()