from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


ReportType = Literal[
    "executive_summary",
    "sales_performance",
    "marketing_campaign",
    "quarterly_summary",
    "product_analysis",
    "regional_analysis",
    "custom",
]


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("Password must include at least one letter and one number")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: EmailStr
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    message: str


class ReportFilters(BaseModel):
    region: str | None = Field(default=None, max_length=80)
    quarter: str | None = Field(default=None, max_length=30)
    product: str | None = Field(default=None, max_length=120)
    channel: str | None = Field(default=None, max_length=120)

    def cleaned(self) -> dict[str, str]:
        return {
            key: value.strip()
            for key, value in self.model_dump().items()
            if isinstance(value, str) and value.strip()
        }


class GenerateReportRequest(BaseModel):
    report_type: ReportType
    dataset_id: str | None = Field(default=None, max_length=36)
    filters: ReportFilters = Field(default_factory=ReportFilters)
    focus: str = Field(default="", max_length=800)
    question: str = Field(default="", max_length=1000)

    @field_validator("focus", "question")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class ReportListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    report_type: str
    dataset_id: str | None
    summary: str
    provider: str
    report_filters: dict
    favorite: bool
    created_at: datetime


class ReportDetail(ReportListItem):
    content: str
    metrics: dict
    chart_data: dict
    insights: list
    updated_at: datetime


class FavoriteRequest(BaseModel):
    favorite: bool


class DeliveryRequest(BaseModel):
    channel: Literal["email", "telegram"]
    destination: str = Field(min_length=2, max_length=320)


class DatasetListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    original_filename: str
    kind: str
    status: str
    row_count: int
    columns: list[str]
    column_types: dict[str, str]
    mapping: dict[str, str]
    created_at: datetime


class DatasetDetail(DatasetListItem):
    preview: list[dict]


class DatasetMappingRequest(BaseModel):
    kind: Literal["sales", "marketing"]
    mapping: dict[str, str]

    @field_validator("mapping")
    @classmethod
    def limit_mapping(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 12:
            raise ValueError("Too many mapped fields")
        return {str(key).strip(): str(item).strip() for key, item in value.items() if item}
