"""iCalendar (RFC 5545) and Google Calendar link generation."""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


def event_bounds(event, tz_name):
    """Return (start, end) as aware UTC datetimes, or dates for all-day events.

    All-day end is returned exclusive (day after the last day), per iCal/Google.
    """
    start = datetime.fromisoformat(event["start_local"])
    end = datetime.fromisoformat(event["end_local"])
    if event["all_day"]:
        return start.date(), end.date() + timedelta(days=1)
    tz = ZoneInfo(tz_name)
    return (
        start.replace(tzinfo=tz).astimezone(timezone.utc),
        end.replace(tzinfo=tz).astimezone(timezone.utc),
    )


def _fmt(value):
    if isinstance(value, datetime):
        return value.strftime("%Y%m%dT%H%M%SZ")
    return value.strftime("%Y%m%d")


def _escape(text):
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line):
    """Fold lines longer than 75 octets without splitting UTF-8 characters."""
    out, current = [], ""
    for ch in line:
        limit = 75 if not out else 74  # continuation lines start with a space
        if len((current + ch).encode("utf-8")) > limit:
            out.append(current)
            current = ch
        else:
            current += ch
    out.append(current)
    return "\r\n ".join(out)


def _description(event):
    desc = event["description"] or ""
    if event["organizer"] and "@" not in event["organizer"]:
        desc = (desc + "\n\n" if desc else "") + f"Organizer: {event['organizer']}"
    if event["url"]:
        desc = (desc + "\n\n" if desc else "") + event["url"]
    return desc


def build_calendar(building, events):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Building Events//MVP//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(building['name'])}",
    ]
    for e in events:
        start, end = event_bounds(e, building["timezone"])
        modified = datetime.fromisoformat(e["updated_at"]).strftime("%Y%m%dT%H%M%SZ")
        # SEQUENCE must increase on edits; seconds since creation is monotonic enough.
        sequence = int(
            (datetime.fromisoformat(e["updated_at"]) - datetime.fromisoformat(e["created_at"])).total_seconds()
        )
        lines += ["BEGIN:VEVENT", f"UID:{e['uid']}", f"DTSTAMP:{stamp}"]
        if e["all_day"]:
            lines += [f"DTSTART;VALUE=DATE:{_fmt(start)}", f"DTEND;VALUE=DATE:{_fmt(end)}"]
        else:
            lines += [f"DTSTART:{_fmt(start)}", f"DTEND:{_fmt(end)}"]
        lines.append(f"SUMMARY:{_escape(e['title'])}")
        if desc := _description(e):
            lines.append(f"DESCRIPTION:{_escape(desc)}")
        if e["location"]:
            lines.append(f"LOCATION:{_escape(e['location'])}")
        if e["url"]:
            lines.append(f"URL:{e['url']}")
        if e["organizer"] and "@" in e["organizer"]:
            lines.append(f"ORGANIZER;CN={_escape(e['organizer'])}:mailto:{e['organizer']}")
        lines += [f"SEQUENCE:{sequence}", f"LAST-MODIFIED:{modified}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


def google_link(event, tz_name):
    start, end = event_bounds(event, tz_name)
    params = {
        "action": "TEMPLATE",
        "text": event["title"],
        "dates": f"{_fmt(start)}/{_fmt(end)}",
        "details": _description(event),
        "location": event["location"] or "",
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def is_upcoming(event, tz_name):
    _, end = event_bounds(event, tz_name)
    if isinstance(end, datetime):
        return end >= datetime.now(timezone.utc)
    return end > datetime.now(ZoneInfo(tz_name)).date()
