import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

import db
from routes import auth, host, public
from web import BASE_DIR, LoginRequired, render


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="The Neighborhood", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "dev-only-change-me"),
                   same_site="lax", max_age=60 * 60 * 24 * 30)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.include_router(auth.router)
app.include_router(host.router)
app.include_router(public.router)


@app.exception_handler(LoginRequired)
async def redirect_to_login(request: Request, _exc: LoginRequired):
    return RedirectResponse(f"{request.url_for('login_page')}?next={request.url.path}", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        response = render(request, "not_found.html")
        response.status_code = 404
        return response
    return HTMLResponse(f"<p>{exc.detail}</p>", status_code=exc.status_code)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5050)),
                reload=True)
