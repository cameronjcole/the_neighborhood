# The Neighborhood — MVP Spec

## 1. Summary

A small web app where apartment building managers ("hosts") publish events for their building, and attendees open a shared link or QR code to see those events and add any or all of them to their calendar.

Two interfaces:

| Interface | Who | Auth | Purpose |
|---|---|---|---|
| **Host dashboard** | Building owners and managers | Email + password | Manage buildings and events, get a share link and QR code |
| **Public event page** | Attendees | None (anyone with the link) | View events, select some or all, export to a calendar |

## 2. Goals and non-goals

**Goals (MVP)**
- A host can sign up, log in, and create a building.
- A host can create, edit, and delete events (one-off, entered individually) that persist.
- Each building has one stable public link, plus a QR code (PNG/SVG download and an inline image).
- An attendee can open the link, see full event details, select individual events or all of them, and export:
  - **Apple Calendar / Outlook / any calendar** → one `.ics` file containing the selected events.
  - **Google Calendar** → a per-event "Add to Google" link (Google has no bulk-add URL; for bulk, attendees import the `.ics` file).
  - **Subscribe** (optional bonus) → a `webcal://` feed so the calendar stays in sync as the host adds events.
- Runs locally with no external services.

**Non-goals (for now)**
- RSVP or attendee tracking, capacity limits
- Recurring events (RRULE). Hosts create repeats manually or with "Duplicate"
- Multiple hosts per building, roles, password reset, email
- Payments, notifications, images

## 3. Tech stack

| Concern | Choice | Why |
|---|---|---|
| Backend | **Python 3 + FastAPI** (run by `uvicorn`) | Small and familiar, typed dependencies and form models, easy to grow into a JSON API; deploys to Vercel (serverless Python) later |
| Templates | Jinja2 (server-rendered via `Jinja2Templates`) + a little vanilla JS | No build step |
| DB | **SQLite** (`data.db` file) via the stdlib `sqlite3` module | Zero setup; persists across restarts. Can swap to Supabase Postgres later |
| Auth | Starlette `SessionMiddleware` (signed cookie) + stdlib `hashlib.scrypt` password hashing | No extra auth service |
| QR codes | `segno` (pure Python, no Pillow needed) | Lightweight; outputs SVG and PNG |
| Calendar export | Hand-written iCalendar (RFC 5545) generator | The format is simple; no dependency needed |
| Timezones | stdlib `zoneinfo` | Each building has an IANA timezone, and ICS times are emitted in UTC |

Deployment path (later): Supabase for Postgres and auth, plus Vercel or Fly.io for the FastAPI app. Keep all DB access in one module (`db.py`) so swapping is contained.

## 4. Data model

```
users
  id            INTEGER PK
  email         TEXT UNIQUE NOT NULL
  password_hash TEXT NOT NULL
  created_at    TEXT NOT NULL (ISO-8601 UTC)

buildings
  id            INTEGER PK
  owner_id      INTEGER FK -> users.id
  name          TEXT NOT NULL
  address       TEXT            -- default location for events
  timezone      TEXT NOT NULL   -- IANA, e.g. "America/New_York"
  share_token   TEXT UNIQUE NOT NULL  -- random, url-safe; used in the public URL
  created_at    TEXT NOT NULL

events
  id            INTEGER PK
  building_id   INTEGER FK -> buildings.id ON DELETE CASCADE
  uid           TEXT UNIQUE NOT NULL  -- stable iCal UID (uuid4@host)
  title         TEXT NOT NULL
  description   TEXT
  location      TEXT            -- e.g. "Rooftop lounge, 12th floor"
  start_local   TEXT NOT NULL   -- "YYYY-MM-DDTHH:MM", building timezone
  end_local     TEXT NOT NULL   -- must be > start
  all_day       INTEGER NOT NULL DEFAULT 0
  url           TEXT            -- optional link (signup form, details)
  organizer     TEXT            -- optional display name / contact
  created_at    TEXT NOT NULL
  updated_at    TEXT NOT NULL   -- used for iCal SEQUENCE/DTSTAMP
```

Calendar fields covered: title (SUMMARY), description, location, start and end (DTSTART/DTEND), all-day, URL, organizer, UID, timestamps. That is the standard set both Apple and Google honor.

## 5. Host dashboard

### Routes
| Method | Path | Description |
|---|---|---|
| GET/POST | `/signup` | Create account |
| GET/POST | `/login` | Log in |
| POST | `/logout` | Log out |
| GET | `/dashboard` | List the host's buildings |
| GET/POST | `/buildings/new` | Create building (name, address, timezone) |
| GET | `/buildings/<id>` | Building detail: event list, share link, QR code |
| GET/POST | `/buildings/<id>/edit` | Edit building |
| POST | `/buildings/<id>/regenerate-link` | New `share_token` (old link and QR stop working) |
| GET/POST | `/buildings/<id>/events/new` | Create event (`?copy=<event_id>` prefills it for duplicating) |
| GET/POST | `/events/<id>/edit` | Edit event |
| POST | `/events/<id>/delete` | Delete event |
| GET | `/buildings/<id>/qr.png` / `qr.svg` | QR code of the public URL (download or embed) |

### Building detail page
- Header: building name and address.
- **Share panel**: public URL with a "Copy link" button, QR image, "Download PNG" and "Download SVG", and "Regenerate link" (with a confirm prompt).
- **Events**: upcoming events sorted by start, with past events collapsed below. Each row shows date/time, title, and location, plus Edit, Duplicate, and Delete.
- "New event" button.

### Event form
Fields: title*, start date/time*, end date/time*, all-day toggle (hides the time inputs), location (defaults to building address), description (multi-line), URL, organizer.
Validation: required fields are present, end is after start, and the URL (if given) starts with http(s).

### Access control
All host routes require login. A host can only see and modify buildings they own, and anything else returns 404.

## 6. Public event page (attendees)

### Routes
| Method | Path | Description |
|---|---|---|
| GET | `/b/<share_token>` | Event list page |
| GET | `/b/<share_token>/events.ics?ids=1,2,3` | ICS with the selected events (all upcoming if `ids` is omitted) |
| GET | `/b/<share_token>/feed.ics` | Subscribable feed (all upcoming and recent events) |

An unknown token returns a friendly 404 page.

### Page layout (mobile-first, since most people arrive from a QR scan)
- Building name and address at the top.
- Toolbar: **Select all** checkbox, "N selected" counter, and **Add selected to calendar** button. The button is disabled when nothing is selected.
- Event cards grouped by date. Each card has:
  - checkbox
  - title, date and time range (in the building's timezone, labeled), location, organizer
  - description (line breaks preserved), plus a link if a URL is set
  - per-event actions: **Apple / .ics** and **Google**
- "Add selected" opens a small menu:
  - **Apple Calendar / Outlook (.ics)**: downloads `events.ics?ids=...`. On iOS/macOS this opens straight into Calendar.
  - **Google Calendar**: when one event is selected, opens the Google template URL. When several are selected, downloads the `.ics` and shows a short instruction: "In Google Calendar → Settings → Import, choose this file." (You can't add several events to Google from a link without OAuth.)
- Footer: "Subscribe to this building's calendar" with a `webcal://` link and a "copy feed URL" option for Google ("Other calendars → From URL").
- Only upcoming events are shown (end ≥ now). If there are none: "No upcoming events — check back soon."

### Google Calendar link format
```
https://calendar.google.com/calendar/render?action=TEMPLATE
  &text=<title>&dates=<YYYYMMDDTHHMMSSZ>/<YYYYMMDDTHHMMSSZ>
  &details=<description>&location=<location>
```
All-day events use `dates=YYYYMMDD/YYYYMMDD` (the end date is exclusive).

### ICS format
- `VCALENDAR` with `VERSION:2.0`, `PRODID`, `CALSCALE:GREGORIAN`, `METHOD:PUBLISH`, `X-WR-CALNAME:<building>`.
- Each `VEVENT`: `UID`, `DTSTAMP`, `DTSTART`/`DTEND` (UTC `...Z`, or `;VALUE=DATE` for all-day), `SUMMARY`, `DESCRIPTION`, `LOCATION`, `URL`, `ORGANIZER;CN=...` (only if the organizer is an email, otherwise it is appended to the description), `SEQUENCE`, `LAST-MODIFIED`.
- Text escaping (`\\`, `\;`, `\,`, `\n`), CRLF line endings, lines folded at 75 octets.
- Response: `Content-Type: text/calendar; charset=utf-8`. The download uses `Content-Disposition: attachment; filename="<building>-events.ics"`, and the feed is served inline.
- A stable UID means re-importing updates events instead of duplicating them (in clients that honor it).

## 7. Non-functional
- Runs with `python main.py` (or `uvicorn main:app --reload`), listening on `http://localhost:5050` by default (5000 is taken by AirPlay on macOS).
- The public base URL for QR codes and links is configurable with the `PUBLIC_BASE_URL` env var. It defaults to the request host. To test with a phone on the same Wi-Fi, set it to the machine's LAN IP.
- `SECRET_KEY` comes from an env var, with a dev fallback.
- CSRF: forms include a per-session token checked on POST.
- No JS framework. One small CSS file. Must be usable on a phone.

## 8. Project layout
```
app/
  main.py           # FastAPI app: middleware, static, routers, error handlers
  web.py            # templates, sessions/flash, CSRF, auth + DB dependencies
  forms.py          # Pydantic form models + validation
  db.py             # sqlite connection, schema, queries
  ics.py            # iCalendar + Google link generation
  routes/auth.py    # signup / login / logout
  routes/host.py    # host dashboard (buildings, events, QR)
  routes/public.py  # attendee page + .ics endpoints
  templates/        # Jinja templates
  static/style.css
  static/public.js  # select-all / export logic
  requirements.txt  # fastapi, uvicorn, jinja2, python-multipart, itsdangerous, segno
  README.md
```

## 9. Acceptance checklist
1. Sign up → create building → add 3 events → they survive a server restart.
2. Building page shows a working copy-link and a QR code that resolves to `/b/<token>`.
3. Opening the public link on a phone lists the events with full details.
4. Select all → Apple/.ics downloads one file with 3 VEVENTs that imports cleanly into Apple Calendar and Google Calendar.
5. Selecting one event → Google opens a prefilled event.
6. Editing an event and re-exporting keeps the same UID.
7. Regenerating the link makes the old URL return 404.
8. Host A cannot view or edit Host B's building.
