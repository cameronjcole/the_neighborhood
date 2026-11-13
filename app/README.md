# Building Events (MVP)

Hosts publish building events; residents open a link/QR code and add events to Apple or Google Calendar.
See `../spec_files/SPEC.md` for the full spec.

## Run locally

```bash
cd app
uv venv && uv pip install -r requirements.txt   # or: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py                         # http://localhost:5050
```

1. Go to http://localhost:5050/signup and create a host account.
2. Add a building, then add events.
3. On the building page, copy the share link or download the QR code.

Data is stored in `app/data.db` (SQLite). Delete the file to reset.

## Testing from your phone

QR codes encode the server's URL, so `localhost` won't work from a phone. Bind to your LAN and tell the app its public address:

```bash
HOST=0.0.0.0 PUBLIC_BASE_URL=http://$(ipconfig getifaddr en0):5050 .venv/bin/python main.py
```

## Config (env vars)

| Var | Default | Purpose |
|---|---|---|
| `PORT` / `HOST` | `5050` / `127.0.0.1` | Server bind |
| `PUBLIC_BASE_URL` | request host | Base URL used in share links, QR codes, and feeds |
| `SECRET_KEY` | dev value | Signs the session cookie; **set this in any real deployment** |
| `DB_PATH` | `app/data.db` | SQLite file |
