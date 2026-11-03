"""Builds the context document handed to the Excuse Director."""
import json
from datetime import date, timedelta

from memory import DB_PATH, normalize, past_excuses_for

LEVELS: dict[int, str] = {
    1: "Vague and low-risk. Something like 'something came up'. No details that could be checked.",
    2: "Tied to one real fact from the calendar or weather. Short and believable.",
    3: "A short saga with two or three supporting details that are internally consistent. Still plausible.",
    4: "Pre-emptive. Look at the next seven days of calendar, pick the meetings the user will most want to skip, and propose one excuse per meeting.",
}


def _doc(name: str, body: str) -> str:
    return f"=====  DOCUMENT: {name}  =====\n{body}"


def _calendar_lines(calendar_path: str, today: date) -> str:
    try:
        with open(calendar_path, encoding="utf-8") as f:
            events = json.load(f)
        end = today + timedelta(days=6)
        lines = []
        for e in sorted(events, key=lambda e: (e["date"], e.get("time", ""))):
            if today <= date.fromisoformat(e["date"]) <= end:
                who = ", ".join(e.get("attendees", []))
                lines.append(f"{e['date']} {e.get('time', '')} {e['title']} ({who})")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return "(calendar unavailable)"
    return "\n".join(lines) if lines else "(no events)"


def build_context(request: str, recipient: str, level: int, city: str = "London",
                  today: date | None = None, calendar_path: str = "data/calendar.json",
                  db_path: str = DB_PATH) -> str:
    if not request or not request.strip():
        raise ValueError("request must not be blank")
    if not recipient or not recipient.strip():
        raise ValueError("recipient must not be blank")
    if level not in LEVELS:
        raise ValueError("level must be 1 to 4")
    today = today or date.today()

    request_md = (
        f"Today: {today.isoformat()}\n"
        f"Escape: {request.strip()}\n"
        f"Recipient: {recipient.strip()}\n"
        f"Level: {level}\n{LEVELS[level]}\n"
        f"City: {city}"
    )
    past = past_excuses_for(normalize(recipient), db_path)
    past_md = "\n".join(f"- {p}" for p in past) if past else "(none)"
    return "\n\n".join([
        _doc("request.md", request_md),
        _doc("calendar.md", _calendar_lines(calendar_path, today)),
        _doc("past-excuses.md", past_md),
    ])
