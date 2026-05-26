from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoomEquipmentResponse(BaseModel):
    id: str
    room_id: str
    name: str
    quantity: int
    note: str | None

    model_config = ConfigDict(from_attributes=True)


class MeetingRoomResponse(BaseModel):
    id: str
    name: str
    location: str
    status: str
    dept_code: str
    equipment: list[RoomEquipmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class MeetingRoomCreate(BaseModel):
    name: str
    location: str
    dept_code: str

    @field_validator("name")
    @classmethod
    def name_max_length(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError("회의실명은 100자 이하여야 합니다")
        return v

    @field_validator("location")
    @classmethod
    def location_max_length(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("위치는 200자 이하여야 합니다")
        return v


class MeetingRoomUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    status: str | None = None
    dept_code: str | None = None


class MeetingRoomUpdateResponse(BaseModel):
    room: MeetingRoomResponse
    warnings: list[str] = []


class RoomEquipmentCreate(BaseModel):
    name: str
    quantity: int = Field(ge=1)
    note: str | None = None

    @field_validator("name")
    @classmethod
    def name_max_length(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError("집기명은 100자 이하여야 합니다")
        return v


class RoomEquipmentUpdate(BaseModel):
    name: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    note: str | None = None


class ScheduleSlot(BaseModel):
    meeting_id: str
    title: str
    start_time: str
    end_time: str
