from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


# ── Department ────────────────────────────────────────────────────────────────


class DepartmentCreate(BaseModel):
    code: str
    name: str


class DepartmentUpdate(BaseModel):
    name: str | None = None
    status: str | None = None


class DepartmentResponse(BaseModel):
    code: str
    name: str
    status: str

    model_config = ConfigDict(from_attributes=True)


# ── Team ──────────────────────────────────────────────────────────────────────


class TeamCreate(BaseModel):
    code: str
    name: str
    dept_code: str


class TeamUpdate(BaseModel):
    name: str | None = None
    dept_code: str | None = None
    status: str | None = None


class TeamResponse(BaseModel):
    code: str
    name: str
    dept_code: str
    status: str

    model_config = ConfigDict(from_attributes=True)


# ── Employee ──────────────────────────────────────────────────────────────────


class EmployeeResponse(BaseModel):
    emp_no: str
    name: str
    dept_code: str
    team_code: str | None
    rank: str | None
    status: str
    is_admin: bool
    is_room_manager: bool

    model_config = ConfigDict(from_attributes=True)


class EmployeeUpdate(BaseModel):
    name: str | None = None
    dept_code: str | None = None
    team_code: str | None = None
    rank: str | None = None


class EmployeeSearchItem(BaseModel):
    emp_no: str
    name: str
    dept_code: str
    dept_name: str
    rank: str | None

    model_config = ConfigDict(from_attributes=True)
