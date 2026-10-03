"""
Schematy Pydantic (DTO) odzwierciedlające dosłownie kontrakty żądań
i odpowiedzi z sekcji 3.9 specyfikacji.
"""
import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

_NAME_RE = re.compile(r"^[A-Za-zÀ-ſ\-]{2,}$")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    firstName: str = Field(min_length=2, max_length=64)
    lastName: str = Field(min_length=2, max_length=64)
    role: Literal["STUDENT", "TUTOR"] = "STUDENT"

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        # RB-B2: min. 8 znaków, przynajmniej jedna cyfra i jeden znak specjalny.
        if not re.search(r"\d", v) or not re.search(r"[^\w\s]", v):
            raise ValueError("COMPLEXITY_REQUIREMENT_NOT_MET")
        return v

    @field_validator("firstName", "lastName")
    @classmethod
    def name_format(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError("INVALID_FORMAT")
        return v


class RegisterResponse(BaseModel):
    userId: uuid.UUID
    email: str
    status: str
    message: str = "Link aktywacyjny wysłany na podany adres e-mail"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    rememberMe: bool = False


class LoginResponse(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: str = "Bearer"
    expiresIn: int
    role: str


class RefreshRequest(BaseModel):
    refreshToken: str


class RefreshResponse(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: str = "Bearer"
    expiresIn: int


class LogoutRequest(BaseModel):
    refreshToken: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    newPassword: str = Field(min_length=8)

    @field_validator("newPassword")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not re.search(r"\d", v) or not re.search(r"[^\w\s]", v):
            raise ValueError("COMPLEXITY_REQUIREMENT_NOT_MET")
        return v


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str = Field(min_length=8)

    @field_validator("newPassword")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not re.search(r"\d", v) or not re.search(r"[^\w\s]", v):
            raise ValueError("COMPLEXITY_REQUIREMENT_NOT_MET")
        return v


class UpdateProfileRequest(BaseModel):
    firstName: str | None = Field(default=None, min_length=2, max_length=64)
    lastName: str | None = Field(default=None, min_length=2, max_length=64)
    avatarUrl: str | None = None
    # Uczeń:
    learningGoals: str | None = Field(default=None, max_length=1000)
    # Korepetytor:
    bio: str | None = Field(default=None, max_length=3000)
    hourlyRate: float | None = Field(default=None, gt=0)
    education: str | None = None
    experienceYears: int | None = Field(default=None, ge=0)
    # Wspólne:
    subjects: list[str] | None = None
    educationLevel: str | None = None


class VerifyPhoneRequest(BaseModel):
    phoneNumber: str
    smsCode: str


class UserAccountResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    verificationStatus: str = Field(validation_alias="verification_status")
    createdAt: datetime = Field(validation_alias="created_at")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ErrorDetail(BaseModel):
    field: str
    code: str
    message: str | None = None


class ErrorResponse(BaseModel):
    error: str
    message: str | None = None
    details: list[ErrorDetail] | None = None
