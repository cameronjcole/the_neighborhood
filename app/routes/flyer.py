"""Flyer import: upload an image/PDF, let Claude extract events, review them, then save."""
import base64
from datetime import datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse

import db
import flyer
from forms import EventForm
from routes.host import owned_building
from web import DB, UserId, flash, render, verify_csrf

router = APIRouter(dependencies=[Depends(verify_csrf)])

ROW_FIELDS = ("title", "start_date", "start_time", "end_date", "end_time", "location", "description")


def review_row(e: flyer.ExtractedEvent, today: str) -> dict:
    """Turn an extracted event into the flat form fields the review page edits."""
    end_date = e.end_date or e.start_date
    start_time, end_time, estimated = e.start_time or "", e.end_time or "", False
    if not e.all_day and start_time and not end_time:
        # Flyer gave a start but no end; default to one hour and flag it for the host.
        start = datetime.fromisoformat(f"{e.start_date}T{start_time}")
        end_time = (start + timedelta(hours=1)).strftime("%H:%M")
        estimated = True
    return {
        # Attendees only see upcoming events, so events that already happened start unticked.
        "include": end_date >= today,
        "title": e.title,
        "all_day": e.all_day or not start_time,
        "start_date": e.start_date,
        "start_time": start_time,
        "end_date": end_date,
        "end_time": end_time,
        "location": e.location or "",
        "description": e.description or "",
        "end_estimated": estimated,
        "errors": [],
    }


def building_today(building) -> str:
    return datetime.now(ZoneInfo(building["timezone"])).date().isoformat()


def render_review(request, building, rows, warnings=(), preview=None, errors=None):
    return render(request, "flyer_review.html", building=building, rows=rows, warnings=warnings,
                  preview=preview, today=building_today(building), errors=errors or [])


@router.get("/buildings/{building_id}/import")
def flyer_upload_page(request: Request, con: DB, user_id: UserId, building_id: int):
    building = owned_building(con, building_id, user_id)
    return render(request, "flyer_upload.html", building=building)


@router.post("/buildings/{building_id}/import")
def flyer_upload(request: Request, con: DB, user_id: UserId, building_id: int,
                 file: Annotated[UploadFile, File()]):
    building = owned_building(con, building_id, user_id)
    data = file.file.read()
    if not data:
        return render(request, "flyer_upload.html", building=building, errors=["Choose a flyer to upload."])
    try:
        extraction = flyer.extract_events(data, building)
    except flyer.FlyerError as e:
        return render(request, "flyer_upload.html", building=building, errors=[str(e)])

    if not extraction.events:
        reason = extraction.warnings[0] if extraction.warnings else "Try a clearer photo or a different file."
        return render(request, "flyer_upload.html", building=building, errors=[f"No events found. {reason}"])

    media_type = flyer.detect_media_type(data)
    preview = None
    if media_type.startswith("image/"):
        preview = f"data:{media_type};base64,{base64.standard_b64encode(data).decode()}"
    rows = [review_row(e, building_today(building)) for e in extraction.events]
    warnings = list(extraction.warnings)
    past = sum(not r["include"] for r in rows)
    if past == len(rows):
        warnings.append("All of these events have already happened, so they start unticked. "
                        "Attendees only see upcoming events, but you can tick any you still want to add.")
    elif past:
        warnings.append(f"{past} of these events {'has' if past == 1 else 'have'} already happened, so "
                        f"{'it starts' if past == 1 else 'they start'} unticked. Attendees only see upcoming events.")
    return render_review(request, building, rows, warnings, preview)


@router.post("/buildings/{building_id}/import/confirm")
async def flyer_confirm(request: Request, con: DB, user_id: UserId, building_id: int):
    building = owned_building(con, building_id, user_id)
    form = await request.form()
    count = int(form.get("count", 0))

    rows, to_save = [], []
    for i in range(count):
        row = {f: str(form.get(f"events-{i}-{f}", "")) for f in ROW_FIELDS}
        row["include"] = form.get(f"events-{i}-include") == "on"
        row["all_day"] = form.get(f"events-{i}-all_day") == "on"
        row["end_estimated"] = False
        event_form = EventForm(**{k: row[k] for k in (*ROW_FIELDS, "all_day")})
        row["errors"] = event_form.errors() if row["include"] else []
        rows.append(row)
        if row["include"] and not row["errors"]:
            to_save.append(event_form.cleaned())

    if not any(r["include"] for r in rows):
        return render_review(request, building, rows, errors=["Select at least one event to add."])
    if any(r["errors"] for r in rows):
        return render_review(request, building, rows, errors=["Some events need a fix before they can be added."])

    for data in to_save:
        db.create_event(con, building_id, data)
    flash(request, f"Added {len(to_save)} event{'' if len(to_save) == 1 else 's'} from your flyer.")
    return RedirectResponse(request.url_for("building_detail", building_id=building_id), status_code=303)
