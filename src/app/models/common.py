import datetime
from enum import StrEnum

from pydantic import BaseModel


class DateRange(BaseModel):
    date_from: datetime.date
    date_to: datetime.date


class ChatMessage(BaseModel):
    role: str
    content: str


class DayOfWeek(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"
