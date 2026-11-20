from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_admin
from app.core.database import get_db
from app.models.user import AppUser
from app.schemas.admin_user import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserStatusUpdate,
)
from app.services.admin_user_service import AdminUserService


router = APIRouter(
    prefix="/admin/users",
    tags=["Admin Users"],
)


@router.post(
    "",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    request: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return AdminUserService.create_user(
        db=db,
        request=request,
    )


@router.get(
    "",
    response_model=list[AdminUserResponse],
)
def get_users(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return AdminUserService.get_users(db)


@router.patch(
    "/{user_id}/status",
    response_model=AdminUserResponse,
)
def update_user_status(
    user_id: int,
    request: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return AdminUserService.update_status(
        db=db,
        user_id=user_id,
        is_active=request.is_active,
        current_user=current_user,
    )