from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.core.response import ApiResponse


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=2048)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class AuthResponse(ApiResponse):
    data: TokenPairResponse | None = None


class UserRead(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    # ORM -> schema donusum icin
    model_config = ConfigDict(from_attributes=True)
