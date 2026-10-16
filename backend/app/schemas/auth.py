"""Authentication schemas for request/response validation."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PasswordSchema(BaseModel):
    @field_validator("password", "new_password", check_fields=False)
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        return value


class UserCreate(PasswordSchema):
    """Schema for user registration."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""

    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool = False

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    """Schema for authentication response with user info."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordChange(PasswordSchema):
    """Schema for password change request."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class RefreshTokenRequest(BaseModel):
    """Legacy refresh body accepted during migration to the HttpOnly cookie."""

    refresh_token: str | None = None
