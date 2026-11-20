from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import AppUser
from app.schemas.admin_user import AdminUserCreate


class AdminUserService:

    @staticmethod
    def create_user(
        db: Session,
        request: AdminUserCreate,
    ) -> AppUser:

        email = str(request.email).strip().lower()
        role = request.role.strip().upper()

        if role not in {"ADMIN", "VIEWER"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be ADMIN or VIEWER",
            )

        existing = db.scalar(
            select(AppUser).where(
                func.lower(AppUser.email) == email
            )
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists",
            )

        user = AppUser(
            email=email,
            full_name=(
                request.full_name.strip()
                if request.full_name
                else None
            ),
            password_hash=hash_password(
                request.temporary_password
            ),
            role=role,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def get_users(
        db: Session,
    ) -> list[AppUser]:

        return list(
            db.scalars(
                select(AppUser).order_by(
                    AppUser.email.asc()
                )
            ).all()
        )

    @staticmethod
    def update_status(
        db: Session,
        user_id: int,
        is_active: bool,
        current_user: AppUser,
    ) -> AppUser:

        user = db.get(
            AppUser,
            user_id,
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Prevent an administrator from accidentally
        # disabling their own current account.
        if user.id == current_user.id and not is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot disable your own account",
            )

        user.is_active = is_active

        db.commit()
        db.refresh(user)

        return user