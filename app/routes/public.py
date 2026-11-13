"""Attendee-facing pages. No login; access is by the building's share token."""
import re
from datetime import datetime, timedelta, timezone
from itertools import groupby
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

import db
import ics
from web import DB, public_base, render, slugify, tz_label

router = APIRouter(prefix="/b")


def building_by_token(con, token):
    building = db.get_building_by_token(con, token)
    if building is None:
        raise HTTPException(404)
    return building


def calendar_response(building, events, download: bool):
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{slugify(building["name"])}-events.ics"'
    return Response(ics.build_calendar(building, events), media_type="text/calendar; charset=utf-8",
                    headers=headers)


@router.get("/{token}")
def public_events(request: Request, con: DB, token: str):
    building = building_by_token(con, token)
    tz = building["timezone"]
    events = [e for e in db.list_events(con, building["id"]) if ics.is_upcoming(e, tz)]
    cards = [dict(e, google_url=ics.google_link(e, tz)) for e in events]
    days = [(day, list(items)) for day, items in groupby(cards, key=lambda e: e["start_local"][:10])]
    feed_url = f"{public_base(request)}/b/{token}/feed.ics"
    return render(request, "public.html", building=building, days=days, count=len(cards), tz=tz_label(tz),
                  feed_url=feed_url, webcal_url=re.sub(r"^https?://", "webcal://", feed_url))


@router.get("/{token}/events.ics")
def public_ics(con: DB, token: str, ids: str = ""):
    """Selected events (?ids=1,2,3), or all upcoming events when no ids are given."""
    building = building_by_token(con, token)
    events = db.list_events(con, building["id"])
    wanted = {int(i) for i in ids.split(",") if i.strip().isdigit()}
    if wanted:
        events = [e for e in events if e["id"] in wanted]
    else:
        events = [e for e in events if ics.is_upcoming(e, building["timezone"])]
    return calendar_response(building, events, download=True)


@router.get("/{token}/feed.ics")
def public_feed(con: DB, token: str):
    """Subscribable feed: upcoming events plus the last 30 days."""
    building = building_by_token(con, token)
    tz = ZoneInfo(building["timezone"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    events = [e for e in db.list_events(con, building["id"])
              if datetime.fromisoformat(e["end_local"]).replace(tzinfo=tz) >= cutoff]
    return calendar_response(building, events, download=False)
