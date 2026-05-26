from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class AttendeeItem(BaseModel):
    emp_no: str
    name: str
    dept_code: str
    rank: str | None

    model_config = ConfigDict(from_attributes=True)


class MeetingCreate(BaseModel):
    title: str
    room_id: str
    meeting_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    agenda: str | None = None

    @field_validator("title")
    @classmethod
    def title_max_length(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("회의명은 200자 이하여야 합니다")
        return v

    @field_validator("agenda")
    @classmethod
    def agenda_max_length(cls, v: str | None) -> str | None:
        if v and len(v) > 2000:
            raise ValueError("의제는 2000자 이하여야 합니다")
        return v

    @model_validator(mode="after")
    def check_times(self) -> MeetingCreate:
        if self.end_time <= self.start_time:
            raise ValueError("종료 시간은 시작 시간보다 늦어야 합니다")
        return self


class MeetingUpdate(BaseModel):
    title: str | None = None
    room_id: str | None = None
    meeting_date: datetime.date | None = None
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    agenda: str | None = None

    @model_validator(mode="after")
    def check_times(self) -> MeetingUpdate:
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("종료 시간은 시작 시간보다 늦어야 합니다")
        return self


class MeetingResponse(BaseModel):
    id: str
    title: str
    room_id: str
    room_name: str
    meeting_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    status: str
    agenda: str | None
    created_by: str
    created_by_name: str
    attendees: list[AttendeeItem] = []

    model_config = ConfigDict(from_attributes=True)


class MeetingListItem(BaseModel):
    id: str
    title: str
    room_name: str
    meeting_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    status: str
    attendee_count: int

    model_config = ConfigDict(from_attributes=True)


class PaginatedMeetings(BaseModel):
    items: list[MeetingListItem]
    total: int
    page: int
    size: int
    pages: int


class AttendeeAdd(BaseModel):
    emp_no: str
