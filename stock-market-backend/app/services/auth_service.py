from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session


from app.models.user import AppUser
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)


class AuthService:

    @staticmethod
    def authenticate(
            db: Session,
            email: str,
            password: str,
    ) -> tuple[AppUser, str]:

        normalized_email = email.strip().lower()

        user = db.scalar(
            select(AppUser).where(
                func.lower(AppUser.email) == normalized_email
            )
        )

        # Keep the same response for unknown email and wrong password.
        if user is None or not verify_password(
                password,
                user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )

        user.last_login_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        )

        db.commit()
        db.refresh(user)

        token = create_access_token(
            subject=user.email,
            additional_claims={
                "user_id": user.id,
                "role": user.role,
            },
        )

        return user, token

    @staticmethod
    def change_password(
        db: Session,
        current_user: AppUser,
        current_password: str,
        new_password: str,
    ) -> None:

        if not verify_password(
            current_password,
            current_user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        if verify_password(
            new_password,
            current_user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password",
            )

        current_user.password_hash = hash_password(new_password)

        db.commit()