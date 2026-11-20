from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserCreate(BaseModel):
    email: EmailStr
    full_name: str | None = Field(
        default=None,
        max_length=255,
    )
    temporary_password: str = Field(
        min_length=8,
        max_length=72,
    )
    role: str = "VIEWER"


class AdminUserStatusUpdate(BaseModel):
    is_active: bool


class AdminUserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None

    model_config = ConfigDict(from_attributes=True)