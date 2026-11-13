"""Read an event flyer (image or PDF) with Claude and extract its events as structured data."""
import base64
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-sonnet-5-5"
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # Claude's per-image limit
MAX_PDF_BYTES = 20 * 1024 * 1024

# Magic-byte prefixes -> media type. We sniff instead of trusting the browser's content type.
SIGNATURES = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
]


ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
API_KEY_VAR = "AI_APIK"


def read_api_key() -> str | None:
    """The Anthropic API key from the AI_APIK env var, else from app/.env (KEY=value or KEY:value lines)."""
    if key := os.environ.get(API_KEY_VAR):
        return key.strip()
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                name, sep, value = line.partition("=") if "=" in line else line.partition(":")
                if sep and name.strip() == API_KEY_VAR:
                    return value.strip().strip("'\"") or None
    except FileNotFoundError:
        pass
    return None


def make_client() -> anthropic.Anthropic:
    # Without AI_APIK, the SDK falls back to its usual lookup (ANTHROPIC_API_KEY, etc.).
    key = read_api_key()
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


class FlyerError(Exception):
    """A problem worth showing to the host as-is (bad file, API unavailable, etc.)."""


class ExtractedEvent(BaseModel):
    title: str = Field(description="Event name as printed, in natural title case.")
    start_date: str = Field(description="YYYY-MM-DD")
    end_date: str | None = Field(description="YYYY-MM-DD if the event spans multiple days, else null.")
    start_time: str | None = Field(description="24-hour HH:MM, or null if no time is printed.")
    end_time: str | None = Field(description="24-hour HH:MM, or null if no end time is printed.")
    all_day: bool = Field(description="True when no specific time is printed or the event spans whole days.")
    location: str | None = Field(description="Where it happens, as printed but in title case (e.g. 'Lobby').")
    description: str | None = Field(description="The flyer's description text, including fine print such as "
                                                "age limits or 'while supplies last'. Null if none.")


class FlyerExtraction(BaseModel):
    events: list[ExtractedEvent]
    warnings: list[str] = Field(description="Short notes about anything the host should double-check, such as "
                                            "an assumed year or text that was hard to read. Empty if none.")


SYSTEM_PROMPT = """You read event flyers that apartment buildings post for residents and turn them into calendar entries.

Extract every dated event on the flyer, one entry per event. Guidelines:
- Observances or promotions that run for a whole period (e.g. "all month long") are a single all-day event spanning that period.
- An event with a date but no printed time is all-day. Use 24-hour times, and if only a start time is printed, leave the end time null.
- Copy descriptions faithfully and keep fine print (age limits, "while supplies last", RSVP notes). Don't invent details.
- Ignore content that isn't an event: social media handles, contact emails, general disclaimers, logos.
- Flyers often omit the year. If weekdays are printed next to dates, use them to find the matching year; otherwise pick 
the year that puts the events closest to today's date. Either way, add a warning saying which year you assumed. 
Don't warn that events are in the past; the app already flags that.
- If the image isn't an event flyer or has no dated events, return an empty list with a warning explaining why."""


def detect_media_type(data: bytes) -> str:
    for prefix, media_type in SIGNATURES:
        if data.startswith(prefix):
            return media_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise FlyerError("That file type isn't supported. Upload a JPG, PNG, WebP, GIF, or PDF.")


def _content_block(data: bytes, media_type: str) -> dict:
    encoded = base64.standard_b64encode(data).decode("utf-8")
    if media_type == "application/pdf":
        if len(data) > MAX_PDF_BYTES:
            raise FlyerError("That PDF is too large. The limit is 20 MB.")
        return {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": encoded}}
    if len(data) > MAX_IMAGE_BYTES:
        raise FlyerError("That image is too large. The limit is 5 MB. Try exporting it at a smaller size.")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}}


def extract_events(data: bytes, building, client: anthropic.Anthropic | None = None) -> FlyerExtraction:
    """Send the flyer to Claude and return the events it found. Raises FlyerError on any failure."""
    media_type = detect_media_type(data)
    block = _content_block(data, media_type)
    today = datetime.now(ZoneInfo(building["timezone"])).date()
    context = (f"Building: {building['name']}\n"
               f"Address: {building['address'] or 'not set'}\n"
               f"Today's date: {today.isoformat()} ({today.strftime('%A')})\n\n"
               "Extract the events from this flyer.")

    try:
        client = client or make_client()
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [block, {"type": "text", "text": context}]}],
            output_config={"effort": "medium"},
            output_format=FlyerExtraction,
            # If the request is declined by a safety classifier, retry on a fallback model automatically.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        raise FlyerError("Flyer import isn't set up: the Anthropic API key is missing or invalid.")
    except anthropic.RateLimitError:
        raise FlyerError("The flyer reader is busy right now. Please try again in a minute.")
    except anthropic.BadRequestError as e:
        raise FlyerError(f"The flyer couldn't be processed: {e.message}")
    except anthropic.APIStatusError:
        raise FlyerError("The flyer reader had a problem. Please try again.")
    except anthropic.APIConnectionError:
        raise FlyerError("Couldn't reach the flyer reader. Check your internet connection and try again.")
    except TypeError as e:
        # The SDK raises this at request time when no credentials are configured at all.
        if "authentication" not in str(e):
            raise
        raise FlyerError("Flyer import isn't set up: add AI_APIK=<your Anthropic API key> to app/.env.")

    if response.stop_reason == "refusal":
        raise FlyerError("The flyer reader declined to process this file.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise FlyerError("The flyer reader couldn't finish reading this file. Try a clearer or smaller image.")
    return response.parsed_output
