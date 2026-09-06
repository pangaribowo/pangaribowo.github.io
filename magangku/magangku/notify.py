"""Push alerts for high-scoring or newly discovered vacancies.

Channels: console (always available), ntfy.sh (no account needed), Telegram.
All configured through environment variables so nothing secret is committed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .matcher import MatchResult


def _post(url: str, data: bytes, headers: dict[str, str], timeout: int = 15) -> tuple[bool, str]:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def format_digest(results: list[MatchResult], limit: int = 8, title: str = "") -> str:
    if not results:
        return "Tidak ada lowongan baru yang cocok."
    lines = [title] if title else []
    for i, r in enumerate(results[:limit], 1):
        v = r.vacancy
        days = f", sisa {v.days_left}h" if v.days_left is not None else ""
        lines.append(
            f"{i}. [{r.score:.0f}] {v.position} - {v.company} "
            f"({v.location}; {v.registered}/{v.quota}{days})\n   {v.apply_url}"
        )
    if len(results) > limit:
        lines.append(f"...dan {len(results) - limit} lowongan lain.")
    return "\n".join(lines)


def send_ntfy(message: str, title: str = "MagangKu", topic: str | None = None,
              priority: str = "default") -> tuple[bool, str]:
    topic = topic or os.getenv("NTFY_TOPIC", "")
    if not topic:
        return False, "NTFY_TOPIC belum diisi di .env"
    server = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    return _post(
        f"{server}/{topic}",
        message.encode("utf-8"),
        {
            "Title": title.encode("ascii", "ignore").decode() or "MagangKu",
            "Priority": priority,
            "Tags": "briefcase",
            "Click": "https://maganghub.kemnaker.go.id/magang-nasional/lowongan",
        },
    )


def send_telegram(message: str, token: str | None = None,
                  chat_id: str | None = None) -> tuple[bool, str]:
    token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diisi di .env"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message[:4000],
        "disable_web_page_preview": "true",
    }).encode()
    return _post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        payload,
        {"Content-Type": "application/x-www-form-urlencoded"},
    )


def dispatch(results: list[MatchResult], channels: list[str], *,
             title: str = "MagangKu - lowongan cocok") -> dict[str, str]:
    message = format_digest(results, title="")
    out: dict[str, str] = {}
    for channel in channels:
        name = str(channel).strip().casefold()
        if name == "console":
            print(f"\n=== {title} ===\n{message}\n")
            out["console"] = "ok"
        elif name == "ntfy":
            ok, info = send_ntfy(message, title=title)
            out["ntfy"] = "ok" if ok else f"gagal - {info}"
        elif name == "telegram":
            ok, info = send_telegram(f"{title}\n\n{message}")
            out["telegram"] = "ok" if ok else f"gagal - {info}"
        else:
            out[name] = "channel tidak dikenal"
    return out
