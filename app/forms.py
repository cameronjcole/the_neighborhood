"""Form models. Validation returns friendly messages so forms can re-render with input intact."""
import re
from datetime import datetime
from zoneinfo import available_timezones

from pydantic import BaseModel

TIMEZONES = sorted(
    tz for tz in available_timezones()
    if "/" in tz and not tz.startswith(("Etc/", "SystemV/", "posix/", "right/"))
)
DEFAULT_TZ = "America/New_York"


class CredentialsForm(BaseModel):
    email: str = ""
    password: str = ""

    def normalized_email(self) -> str:
        return self.email.strip().lower()

    def signup_errors(self) -> list[str]:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.normalized_email()):
            return ["Enter a valid email."]
        if len(self.password) < 8:
            return ["Password must be at least 8 characters."]
        return []


class BuildingForm(BaseModel):
    name: str = ""
    address: str = ""
    timezone: str = DEFAULT_TZ

    def cleaned(self) -> dict:
        return {"name": self.name.strip(), "address": self.address.strip(), "timezone": self.timezone}

    def errors(self) -> list[str]:
        errors = []
        if not self.name.strip():
            errors.append("Building name is required.")
        if self.timezone not in TIMEZONES:
            errors.append("Pick a valid timezone.")
        return errors


class EventForm(BaseModel):
    title: str = ""
    all_day: bool = False  # HTML checkbox sends "on" when checked, which pydantic reads as True
    start_date: str = ""
    start_time: str = ""
    end_date: str = ""
    end_time: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    organizer: str = ""

    def cleaned(self) -> dict:
        """Map form fields onto the events table columns."""
        end_date = self.end_date or self.start_date
        start_time = "00:00" if self.all_day else self.start_time
        end_time = "00:00" if self.all_day else self.end_time
        return {
            "title": self.title.strip(),
            "description": self.description.strip(),
            "location": self.location.strip(),
            "start_local": f"{self.start_date}T{start_time}",
            "end_local": f"{end_date}T{end_time}",
            "all_day": int(self.all_day),
            "url": self.url.strip(),
            "organizer": self.organizer.strip(),
        }

    def errors(self) -> list[str]:
        data = self.cleaned()
        errors = []
        if not data["title"]:
            errors.append("Title is required.")
        try:
            start = datetime.fromisoformat(data["start_local"])
            end = datetime.fromisoformat(data["end_local"])
            if self.all_day and end < start:
                errors.append("End date can't be before the start date.")
            elif not self.all_day and end <= start:
                errors.append("End time must be after the start time.")
        except ValueError:
            errors.append("Start and end date/time are required.")
        if data["url"] and not re.match(r"https?://", data["url"]):
            errors.append("Link must start with http:// or https://")
        return errors
