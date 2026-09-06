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
        pinned = base_url or os.getenv("MAGANGKU_BASE_URL") or ""
        self._pinned = bool(pinned)
        self._resolved = ""
        self.base_url = (pinned or DEFAULT_BASE).rstrip("/") + "/"
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

    # ------------------------------------------------------------------ #
    def candidate_urls(self) -> list[str]:
        """Vacancy-list URLs to try, best guess first.

        If the user pinned MAGANGKU_BASE_URL (or passed base_url) we honour it
        exclusively - explicit configuration always wins over auto-detection.
        """
        if self._pinned:
            return [self.base_url + VACANCIES_PATH]
        from .endpoints import VACANCY_ENDPOINTS
        seen, urls = set(), []
        for endpoint in VACANCY_ENDPOINTS:
            if endpoint.url not in seen:
                seen.add(endpoint.url)
                urls.append(endpoint.url)
        return urls

    def resolve_url(self) -> str:
        """Pick the first vacancy endpoint that actually returns rows.

        Kemnaker moved MagangHub behind a new gateway (api.kemnaker.go.id) in
        2026 and the old path now demands auth, so we probe instead of assuming.
        The winner is cached for the life of this client.
        """
        if self._resolved:
            return self._resolved
        candidates = self.candidate_urls()
        if len(candidates) == 1:
            self._resolved = candidates[0]
            return self._resolved

        errors: list[str] = []
        saved_retries, self.max_retries = self.max_retries, 1  # probe fast
        saved_level = log.level
        log.setLevel(logging.ERROR)  # probing failures are expected; don't shout
        try:
            for url in candidates:
                try:
                    payload = self._get(url, {"page": 1, "limit": 1})
                except ScrapeError as exc:
                    errors.append(f"  - {url}\n      {str(exc).splitlines()[0]}")
                    continue
                rows = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(rows, list):
                    log.info("Endpoint aktif: %s", url)
                    self._resolved = url
                    return url
                errors.append(f"  - {url}\n      200 tapi tanpa 'data' berbentuk list")
        finally:
            self.max_retries = saved_retries
            log.setLevel(saved_level)

        raise ScrapeError(
            "Tidak ada endpoint lowongan yang merespons.\n"
            + "\n".join(errors)
            + "\n\nKemnaker memindahkan API MagangHub ke gateway baru "
              "(api.kemnaker.go.id) dan endpoint lama kini butuh login.\n"
              "Jalankan `magangku probe` untuk menguji semua kandidat dari mesin "
              "Anda, atau pakai `--source fixtures` untuk bekerja offline."
        )

    def fetch_page(self, page: int = 1, limit: int = 100, **params: Any) -> dict[str, Any]:
        """Fetch one page with exponential backoff. Raises ScrapeError."""
        url = params.pop("_url", None) or self.resolve_url()
        is_legacy = "/be/v1/api/" in url

        query: dict[str, Any] = {"page": page, "limit": limit}
        if is_legacy:
            query["order_by"] = params.pop("order_by", "jumlah_kuota")
            query["order_direction"] = params.pop("order_direction", "DESC")
            query["per_page"] = limit
        else:
            params.pop("order_by", None)
            params.pop("order_direction", None)
            query["per_page"] = limit
        for key, value in params.items():
            if value not in (None, "", []):
                query[key] = value

        return self._get(url, query)

    def _get(self, url: str, query: dict[str, Any]) -> dict[str, Any]:
        """Single GET with retry/backoff, shared by probing and paging."""
        import httpx  # imported lazily so offline use needs no network stack

        page = query.get("page", 1)
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
        url = self.resolve_url()  # resolve once, reuse for every page

        while True:
            if max_pages is not None and fetched >= max_pages:
                break
            payload = self.fetch_page(page=page, limit=limit, _url=url, **params)
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
            # Legacy backend calls it kode_provinsi; the new gateway uses
            # camelCase. Send both - each backend ignores the key it lacks.
            if "/be/v1/api/" in self.resolve_url():
                params["kode_provinsi"] = province
            else:
                params["provinceCode"] = province
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
