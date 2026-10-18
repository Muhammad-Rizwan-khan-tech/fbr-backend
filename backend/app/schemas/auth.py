from pydantic import BaseModel, EmailStr
from typing import Optional


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRegister(BaseModel):
    org_name: str
    full_name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    ntn: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: str
    user_name: str
    org_name: str


class TokenPayload(BaseModel):
    sub: str
    tenant_id: str
    role: str
    exp: int


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    username: Optional[str] = None
    full_name: str
    role: str
    phone: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True
