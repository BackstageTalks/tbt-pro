import os
import re
import unicodedata
from urllib.parse import quote

import requests


RAPID_API_HOST = (
    "tennis-api-atp-wta-itf.p.rapidapi.com"
)

BASE_URL = (
    f"https://{RAPID_API_HOST}"
)

TIMEOUT = 20


def _headers():

    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": RAPID_API_HOST,
        "x-rapidapi-key": os.getenv(
            "RAPIDAPI_KEY",
            ""
        ),
    }


def _participant_slug(name: str) -> str:
    if name is None:
        return ""

    text = str(name).strip()

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = re.sub(
        r"[^A-Za-z0-9]",
        "",
        text,
    )

    return text


def _get_event_id_once(
    participant1: str,
    participant2: str,
    date_only: str,
):
    p1 = quote(
        _participant_slug(participant1),
        safe="",
    )

    p2 = quote(
        _participant_slug(participant2),
        safe="",
    )

    url = (
        f"{BASE_URL}"
        f"/tennis/v2/extend/api/event/get"
        f"/{p1}"
        f"/{p2}"
        f"/{date_only}"
    )

    response = requests.get(
        url,
        headers=_headers(),
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    payload = response.json()

    result = payload.get(
        "result",
        {}
    )

    event_id = result.get(
        "id"
    )

    if not event_id:
        return None

    return str(event_id)


def get_event_id(
    player1: str,
    player2: str,
    date_only: str,
):
    try:
        event_id = _get_event_id_once(
            player1,
            player2,
            date_only,
        )

        if event_id:
            return event_id

    except Exception as exc:
        print(
            "MARQ EVENT ID PRIMARY ERROR:",
            player1,
            "vs",
            player2,
            str(exc),
        )

    try:
        event_id = _get_event_id_once(
            player2,
            player1,
            date_only,
        )

        if event_id:
            return event_id

    except Exception as exc:
        print(
            "MARQ EVENT ID REVERSE ERROR:",
            player2,
            "vs",
            player1,
            str(exc),
        )

    return None


def get_odds_summary(
    event_id: str,
):
    url = (
        f"{BASE_URL}"
        f"/tennis/v2/extend/api/odds/summary"
        f"/{event_id}"
    )

    try:

        response = requests.get(
            url,
            headers=_headers(),
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        return response.json()

    except Exception as exc:

        print(
            "MARQ ODDS SUMMARY ERROR:",
            str(exc),
        )

        return None


def get_recent_odds(
    event_id: str,
):
    url = (
        f"{BASE_URL}"
        f"/tennis/v2/extend/api/event/recent-odds/get"
        f"/{event_id}"
    )

    try:

        response = requests.get(
            url,
            headers=_headers(),
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        return response.json()

    except Exception as exc:

        print(
            "MARQ RECENT ODDS ERROR:",
            str(exc),
        )

        return None
