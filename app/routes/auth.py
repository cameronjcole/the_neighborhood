import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

import db
from forms import CredentialsForm
from web import DB, check_password, flash, hash_password, render, verify_csrf

router = APIRouter(dependencies=[Depends(verify_csrf)])


@router.get("/")
def index(request: Request):
    target = "dashboard" if "user_id" in request.session else "login"
    return RedirectResponse(request.url_for(target), status_code=303)


@router.get("/signup")
def signup_page(request: Request):
    return render(request, "auth.html", mode="signup", email="")


@router.post("/signup")
def signup(request: Request, con: DB, form: Annotated[CredentialsForm, Form()]):
    errors = form.signup_errors()
    if not errors:
        try:
            request.session["user_id"] = db.create_user(con, form.normalized_email(), hash_password(form.password))
            return RedirectResponse(request.url_for("dashboard"), status_code=303)
        except sqlite3.IntegrityError:
            errors = ["An account with that email already exists."]
    for e in errors:
        flash(request, e)
    return render(request, "auth.html", mode="signup", email=form.email)


@router.get("/login")
def login_page(request: Request):
    return render(request, "auth.html", mode="login", email="")


@router.post("/login")
def login(request: Request, con: DB, form: Annotated[CredentialsForm, Form()], next: str = ""):
    user = db.get_user_by_email(con, form.normalized_email())
    if user and check_password(user["password_hash"], form.password):
        request.session["user_id"] = user["id"]
        safe_next = next if next.startswith("/") and not next.startswith("//") else None
        return RedirectResponse(safe_next or request.url_for("dashboard"), status_code=303)
    flash(request, "Incorrect email or password.")
    return render(request, "auth.html", mode="login", email=form.email)


@router.post("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse(request.url_for("login_page"), status_code=303)
