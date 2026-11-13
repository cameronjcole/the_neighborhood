"""Shared web plumbing: templates, flash messages, sessions, CSRF, auth dependencies."""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime
from typing import Annotated, Iterator
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates

import db

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.filters["pretty_date"] = lambda v: datetime.fromisoformat(v).strftime("%a, %b %-d, %Y")
templates.env.filters["pretty_time"] = lambda v: datetime.fromisoformat(v).strftime("%-I:%M %p")
templates.env.filters["month_abbr"] = lambda v: datetime.fromisoformat(v).strftime("%b")
templates.env.filters["day_num"] = lambda v: datetime.fromisoformat(v).strftime("%-d")
templates.env.filters["month_year"] = lambda v: datetime.fromisoformat(f"{v}-01").strftime("%B %Y")
templates.env.filters["weekday"] = lambda v: datetime.fromisoformat(v).strftime("%A")


# --- database ---

def get_db() -> Iterator[db.Conn]:
    con = db.connect()
    try:
        yield con
    finally:
        con.close()


DB = Annotated[db.Conn, Depends(get_db)]


# --- passwords (stdlib scrypt) ---

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(stored: str, password: str) -> bool:
    _, salt, digest = stored.split("$")
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
    return hmac.compare_digest(candidate.hex(), digest)


# --- sessions, flash, CSRF ---

def flash(request: Request, message: str, category: str = "success"):
    """Queue a toast for the next rendered page. category: "success" or "error"."""
    request.session.setdefault("_flashes", []).append([category, message])


def csrf_token(request: Request) -> str:
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(16)
    return request.session["csrf"]


async def verify_csrf(request: Request):
    """Attach to every router: no-op for safe methods, checks the form token on POST."""
    if request.method == "POST":
        form = await request.form()
        if not hmac.compare_digest(str(form.get("csrf", "")), request.session.get("csrf", "")):
            raise HTTPException(400, "Invalid form token, please reload the page and try again.")


def render(request: Request, name: str, **context):
    context.setdefault("errors", [])
    context |= {
        "csrf_token": csrf_token(request),
        "logged_in": "user_id" in request.session,
        "messages": request.session.pop("_flashes", []),
    }
    return templates.TemplateResponse(request, name, context)


# --- auth ---

class LoginRequired(Exception):
    """Raised by `require_user`; main.py turns it into a redirect to the login page."""


def require_user(request: Request) -> int:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise LoginRequired()
    return user_id


UserId = Annotated[int, Depends(require_user)]


# --- misc helpers ---

def public_base(request: Request) -> str:
    return os.environ.get("PUBLIC_BASE_URL", str(request.base_url)).rstrip("/")


def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower() or "building"


def tz_label(tz_name: str) -> str:
    return datetime.now(ZoneInfo(tz_name)).strftime("%Z")
