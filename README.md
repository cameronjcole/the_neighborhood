# The Neighborhood

A small web app for apartment buildings to share events with the people who live there.

- **Hosts** (building owners/managers) log in, create events, and get a share link and QR code to post in the building.
- **Attendees** open the link or scan the QR code (no login), see upcoming events, and add one, several, or all of them to Apple or Google Calendar.

The full spec is in [spec_files/SPEC.md](spec_files/SPEC.md). The app lives in [app/](app/).

## Quick start

```bash
cd app
uv venv && uv pip install -r requirements.txt
.venv/bin/python main.py
```

Open http://localhost:5050/signup to create a host account. Data is saved to `app/data.db` (SQLite).

To scan the QR code from a phone on the same Wi-Fi:

```bash
HOST=0.0.0.0 PUBLIC_BASE_URL=http://$(ipconfig getifaddr en0):5050 .venv/bin/python main.py
```

## Requirements

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)**: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`). Plain `python3 -m venv` + `pip` also works.
- Python packages are installed from `app/requirements.txt`: FastAPI, Uvicorn, Jinja2, python-multipart, itsdangerous, segno.

Nothing else is needed: no database server, no Node, no API keys.
