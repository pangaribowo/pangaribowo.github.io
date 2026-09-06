"""Polite client for the public Kemnaker MagangHub API.

Endpoint discovered from community projects and verified against archived
payloads:

    GET https://maganghub.kemnaker.go.id/be/v1/api/list/vacancies-aktif
        ?order_by=jumlah_kuota&order_direction=DESC&page=1&limit=100
        [&kode_provinsi=34]

The site sits behind Cloudflare, so some networks (CI runners, sandboxes,
corporate proxies) get connection resets. Every failure path here degrades to a
clear message, and `--source fixtures` lets the whole pipeline run offline.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Iterator

from .models import utcnow_iso
from .normalize import last_page, normalize_payload, page_total
from .models import Vacancy

log = logging.getLogger("magangku.scraper")

DEFAULT_BASE = "https://maganghub.kemnaker.go.id/be/v1/api/"
VACANCIES_PATH = "list/vacancies-aktif"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Referer": "https://maganghub.kemnaker.go.id/magang-nasional/lowongan",
    "Origin": "https://maganghub.kemnaker.go.id",
}


class ScrapeError(RuntimeError):
    """Network/HTTP failure that the CLI should present nicely."""


class MagangHubScraper:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float | None = None,
        delay: float | None = None,
        max_retries: int | None = None,
        cookie: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("MAGANGKU_BASE_URL") or DEFAULT_BASE).rstrip("/") + "/"
        self.timeout = float(timeout if timeout is not None else os.getenv("MAGANGKU_TIMEOUT", 30))
        self.delay = float(delay if delay is not None else os.getenv("MAGANGKU_DELAY", 1.0))
        self.max_retries = int(max_retries if max_retries is not None
                               else os.getenv("MAGANGKU_MAX_RETRIES", 4))
        self.cookie = cookie or os.getenv("MAGANGHUB_COOKIE") or ""

    # ------------------------------------------------------------------ #
    def _headers(self) -> dict[str, str]:
        headers = dict(BROWSER_HEADERS)
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

    def fetch_page(self, page: int = 1, limit: int = 100, **params: Any) -> dict[str, Any]:
        """Fetch one page with exponential backoff. Raises ScrapeError."""
        import httpx  # imported lazily so offline use needs no network stack

        query: dict[str, Any] = {
            "order_by": params.pop("order_by", "jumlah_kuota"),
            "order_direction": params.pop("order_direction", "DESC"),
            "page": page,
            "limit": limit,
            "per_page": limit,
        }
        for key, value in params.items():
            if value not in (None, "", []):
                query[key] = value

        url = self.base_url + VACANCIES_PATH
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True,
                                  headers=self._headers()) as client:
                    resp = client.get(url, params=query)
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except json.JSONDecodeError as exc:
                        raise ScrapeError(
                            "Server membalas bukan JSON (kemungkinan halaman "
                            "challenge Cloudflare). Coba lagi dari jaringan biasa "
                            "atau gunakan --source fixtures."
                        ) from exc
                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = min(30.0, 2.0 ** attempt)
                    log.warning("HTTP %s pada halaman %s, tunggu %.1fs (percobaan %s/%s)",
                                resp.status_code, page, wait, attempt, self.max_retries)
                    time.sleep(wait)
                    continue
                raise ScrapeError(f"HTTP {resp.status_code} dari {url}")
            except ScrapeError:
                raise
            except Exception as exc:  # network-level failure
                last_exc = exc
                wait = min(20.0, 1.5 * attempt)
                log.warning("Gagal ambil halaman %s (%s). Ulang dalam %.1fs",
                            page, type(exc).__name__, wait)
                if attempt < self.max_retries:
                    time.sleep(wait)

        raise ScrapeError(
            f"Tidak bisa menghubungi {url} setelah {self.max_retries} percobaan. "
            f"Penyebab terakhir: {type(last_exc).__name__}: {last_exc}\n"
            "MagangHub dilindungi Cloudflare dan sering memblokir IP datacenter/VPN.\n"
            "Solusi: jalankan dari koneksi rumah/kantor, atau pakai data offline "
            "dengan `--source fixtures`."
        )

    # ------------------------------------------------------------------ #
    def iter_pages(
        self,
        *,
        limit: int = 100,
        max_pages: int | None = None,
        start_page: int = 1,
        on_page: Callable[[int, int, int], None] | None = None,
        **params: Any,
    ) -> Iterator[dict[str, Any]]:
        page, fetched = start_page, 0
        total_pages: int | None = None

        while True:
            if max_pages is not None and fetched >= max_pages:
                break
            payload = self.fetch_page(page=page, limit=limit, **params)
            payload["_scraped_at"] = utcnow_iso()

            rows = payload.get("data") if isinstance(payload, dict) else None
            if not rows:
                break

            if total_pages is None:
                total_pages = last_page(payload) or 0
            fetched += 1
            if on_page:
                on_page(page, total_pages or 0, page_total(payload))

            yield payload

            if total_pages and page >= total_pages:
                break
            page += 1
            if self.delay:
                time.sleep(self.delay)

    def scrape(
        self,
        *,
        limit: int = 100,
        max_pages: int | None = None,
        province: str | None = None,
        raw_dir: Path | None = None,
        on_page: Callable[[int, int, int], None] | None = None,
    ) -> list[Vacancy]:
        params: dict[str, Any] = {}
        if province:
            params["kode_provinsi"] = province

        out: list[Vacancy] = []
        for idx, payload in enumerate(
            self.iter_pages(limit=limit, max_pages=max_pages, on_page=on_page, **params), 1
        ):
            if raw_dir:
                raw_dir.mkdir(parents=True, exist_ok=True)
                tag = province or "all"
                (raw_dir / f"vacancies_prov{tag}_{idx}.json").write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
            out.extend(normalize_payload(payload))
        return out


# --------------------------------------------------------------------------- #
# Offline sources
# --------------------------------------------------------------------------- #
def load_from_dir(directory: Path) -> list[Vacancy]:
    """Load every `*.json` API page in a directory into Vacancy objects."""
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Direktori data tidak ditemukan: {directory}")

    files = sorted(p for p in directory.glob("*.json") if p.name != "provinces.json")
    if not files:
        raise FileNotFoundError(f"Tidak ada file .json di {directory}")

    out: list[Vacancy] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            log.warning("Lewati %s: JSON tidak valid (%s)", path.name, exc)
            continue
        out.extend(normalize_payload(payload))
    return out


def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "fixtures"


def load_fixtures() -> list[Vacancy]:
    return load_from_dir(fixtures_dir())


def load_provinces() -> list[dict[str, str]]:
    path = fixtures_dir() / "provinces.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
