import os

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.security import verify_password
from app.models.user import AppUser


def main() -> None:
    email = os.environ["BOOTSTRAP_ADMIN_EMAIL"].strip().lower()
    password = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]

    db = SessionLocal()

    try:
        user = db.scalar(
            select(AppUser).where(
                func.lower(AppUser.email) == email
            )
        )

        if user is None:
            print("User found: False")
            return

        print("User found: True")
        print(f"Role: {user.role}")
        print(f"Active: {user.is_active}")
        print(
            "Password matches secret: "
            f"{verify_password(password, user.password_hash)}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()