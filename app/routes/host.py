"""Host dashboard: buildings, events, share link and QR code. Every route requires login."""
import io
from datetime import datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import segno
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

import db
import ics
from forms import DEFAULT_TZ, TIMEZONES, BuildingForm, EventForm
from web import DB, UserId, flash, public_base, render, slugify, tz_label, verify_csrf

router = APIRouter(dependencies=[Depends(verify_csrf)])


def owned_building(con, building_id, user_id):
    building = db.get_building(con, building_id, user_id)
    if building is None:
        raise HTTPException(404)
    return building


def owned_event(con, event_id, user_id):
    event = db.get_event(con, event_id, user_id)
    if event is None:
        raise HTTPException(404)
    return event


def share_url(request: Request, building) -> str:
    return f"{public_base(request)}/b/{building['share_token']}"


def redirect_to_building(request: Request, building_id: int):
    return RedirectResponse(request.url_for("building_detail", building_id=building_id), status_code=303)


# --- buildings ---

@router.get("/dashboard")
def dashboard(request: Request, con: DB, user_id: UserId):
    cards = []
    for b in db.list_buildings(con, user_id):
        upcoming = [e for e in db.list_events(con, b["id"]) if ics.is_upcoming(e, b["timezone"])]
        cards.append(dict(b, upcoming_count=len(upcoming), next_event=upcoming[0] if upcoming else None))
    return render(request, "dashboard.html", buildings=cards)


@router.get("/buildings/new")
def building_new_page(request: Request, user_id: UserId):
    return render(request, "building_form.html", building={"name": "", "address": "", "timezone": DEFAULT_TZ},
                  timezones=TIMEZONES, is_new=True)


@router.post("/buildings/new")
def building_new(request: Request, con: DB, user_id: UserId, form: Annotated[BuildingForm, Form()]):
    if errors := form.errors():
        return render(request, "building_form.html", errors=errors, building=form.cleaned(), timezones=TIMEZONES,
                      is_new=True)
    data = form.cleaned()
    building_id = db.create_building(con, user_id, data["name"], data["address"], data["timezone"])
    return redirect_to_building(request, building_id)


@router.get("/buildings/{building_id}/edit")
def building_edit_page(request: Request, con: DB, user_id: UserId, building_id: int):
    building = owned_building(con, building_id, user_id)
    return render(request, "building_form.html", building=building, timezones=TIMEZONES, is_new=False,
                  building_id=building_id)


@router.post("/buildings/{building_id}/edit")
def building_edit(request: Request, con: DB, user_id: UserId, building_id: int,
                  form: Annotated[BuildingForm, Form()]):
    owned_building(con, building_id, user_id)
    if errors := form.errors():
        return render(request, "building_form.html", errors=errors, building=form.cleaned(), timezones=TIMEZONES,
                      is_new=False, building_id=building_id)
    data = form.cleaned()
    db.update_building(con, building_id, data["name"], data["address"], data["timezone"])
    return redirect_to_building(request, building_id)


@router.get("/buildings/{building_id}")
def building_detail(request: Request, con: DB, user_id: UserId, building_id: int):
    building = owned_building(con, building_id, user_id)
    events = db.list_events(con, building_id)
    upcoming = [e for e in events if ics.is_upcoming(e, building["timezone"])]
    past = [e for e in events if not ics.is_upcoming(e, building["timezone"])]
    return render(request, "building_detail.html", building=building, upcoming=upcoming, past=past,
                  share_url=share_url(request, building), tz=tz_label(building["timezone"]))


@router.post("/buildings/{building_id}/regenerate-link")
def regenerate_link(request: Request, con: DB, user_id: UserId, building_id: int):
    owned_building(con, building_id, user_id)
    db.regenerate_token(con, building_id)
    flash(request, "New link generated. The old link and QR code no longer work.")
    return redirect_to_building(request, building_id)


@router.get("/buildings/{building_id}/qr.{fmt}")
def building_qr(request: Request, con: DB, user_id: UserId, building_id: int,
                fmt: Literal["png", "svg"], download: bool = False):
    building = owned_building(con, building_id, user_id)
    buf = io.BytesIO()
    segno.make(share_url(request, building), error="m").save(buf, kind=fmt, scale=10, border=2)
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{slugify(building["name"])}-events-qr.{fmt}"'
    media_type = "image/png" if fmt == "png" else "image/svg+xml"
    return Response(buf.getvalue(), media_type=media_type, headers=headers)


# --- events ---

def blank_event(building) -> dict:
    tomorrow = datetime.now(ZoneInfo(building["timezone"])).date() + timedelta(days=1)
    return {"title": "", "description": "", "location": building["address"] or "",
            "start_local": f"{tomorrow}T18:00", "end_local": f"{tomorrow}T20:00",
            "all_day": 0, "url": "", "organizer": ""}


@router.get("/buildings/{building_id}/events/new")
def event_new_page(request: Request, con: DB, user_id: UserId, building_id: int, copy: int | None = None):
    building = owned_building(con, building_id, user_id)
    event = blank_event(building)
    if copy is not None:
        source = db.get_event(con, copy, user_id)
        if source and source["building_id"] == building_id:
            event = {k: source[k] for k in db.EVENT_FIELDS}
    return render(request, "event_form.html", building=building, event=event, is_new=True)


@router.post("/buildings/{building_id}/events/new")
def event_new(request: Request, con: DB, user_id: UserId, building_id: int, form: Annotated[EventForm, Form()]):
    building = owned_building(con, building_id, user_id)
    data = form.cleaned()
    if errors := form.errors():
        return render(request, "event_form.html", errors=errors, building=building, event=data, is_new=True)
    db.create_event(con, building_id, data)
    flash(request, f"Added “{data['title']}”.")
    return redirect_to_building(request, building_id)


@router.get("/events/{event_id}/edit")
def event_edit_page(request: Request, con: DB, user_id: UserId, event_id: int):
    event = owned_event(con, event_id, user_id)
    building = owned_building(con, event["building_id"], user_id)
    return render(request, "event_form.html", building=building, event=event, is_new=False, event_id=event_id)


@router.post("/events/{event_id}/edit")
def event_edit(request: Request, con: DB, user_id: UserId, event_id: int, form: Annotated[EventForm, Form()]):
    event = owned_event(con, event_id, user_id)
    building = owned_building(con, event["building_id"], user_id)
    data = form.cleaned()
    if errors := form.errors():
        return render(request, "event_form.html", errors=errors, building=building, event=data, is_new=False,
                      event_id=event_id)
    db.update_event(con, event_id, data)
    flash(request, f"Saved “{data['title']}”.")
    return redirect_to_building(request, building["id"])


@router.post("/events/{event_id}/delete")
def event_delete(request: Request, con: DB, user_id: UserId, event_id: int):
    event = owned_event(con, event_id, user_id)
    db.delete_event(con, event_id)
    flash(request, f"Deleted “{event['title']}”.")
    return redirect_to_building(request, event["building_id"])
