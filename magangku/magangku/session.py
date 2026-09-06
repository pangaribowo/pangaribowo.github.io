"""Local-only session handling for authenticated Kemnaker endpoints.

=============================================================================
KONTRAK KEAMANAN - baca sebelum mengubah apa pun di berkas ini
=============================================================================
1. Modul ini TIDAK PERNAH meminta, menyimpan, atau mengirim password.
2. Token sesi hanya dibaca dari mesin pengguna sendiri:
     - variabel MAGANGHUB_COOKIE di .env, atau
     - session.json yang dibuat pengguna, atau
     - jendela browser yang pengguna login sendiri (opsional).
3. Token diredaksi di SETIAP log, pesan error, dan respons API.
4. Tidak ada data yang dikirim ke mana pun selain domain kemnaker.go.id.
5. Berkas sesi ditulis dengan permission 0600 (hanya pemilik yang bisa baca).
=============================================================================

Cara paling aman & paling andal mendapatkan data profil Anda tetap:
ekspor JSON-nya sendiri dari DevTools browser, lalu
`magangku sync --from-file profil.json`. Tidak ada token yang berpindah
tangan sama sekali.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = ROOT / "session.json"

# Domain yang boleh dihubungi. Apa pun di luar ini ditolak mentah-mentah.
ALLOWED_HOSTS = (
    "api.kemnaker.go.id",            # gateway baru (per 2026) - lihat endpoints.py
    "maganghub.kemnaker.go.id",
    "monev.maganghub.kemnaker.go.id",
    "account.kemnaker.go.id",
    "siapkerja.kemnaker.go.id",
    "karirhub.kemnaker.go.id",
)

# Endpoint kandidat untuk profil peserta.
#
# CATATAN JUJUR: hanya `monev.../api/users/me` yang bentuk responsnya sudah
# terkonfirmasi (dari proyek komunitas maganghub-autopresence). Sisanya adalah
# tebakan berdasarkan pola URL Kemnaker dan BELUM terverifikasi. `sync --auto`
# mencoba satu per satu dan melaporkan mana yang berhasil. Bila semua gagal,
# pakai jalur `--from-file` yang selalu bekerja.
PROFILE_ENDPOINTS = (
    # --- gateway baru (api.kemnaker.go.id) - didahulukan sejak 2026 ---------
    "https://api.kemnaker.go.id/profile/v1/profiles/me",
    "https://api.kemnaker.go.id/v2/users/me",
    "https://api.kemnaker.go.id/maganghub/onboarding/v2/profile",
    # --- backend lama - masih dicoba sebagai cadangan ----------------------
    "https://monev.maganghub.kemnaker.go.id/api/users/me",
    "https://maganghub.kemnaker.go.id/be/v1/api/users/me",
    "https://maganghub.kemnaker.go.id/be/v1/api/profile",
    "https://maganghub.kemnaker.go.id/be/v1/api/peserta/profile",
    "https://account.kemnaker.go.id/api/users/me",
)

# Endpoint daftar lamaran. Yang pertama SUDAH TERKONFIRMASI dari respons nyata
# yang dikirim pengguna (paginasi Laravel, meta.hostname = maganghub-recruitment-*).
APPLICATION_ENDPOINTS = (
    "https://api.kemnaker.go.id/v2/applications/me",
    "https://api.kemnaker.go.id/maganghub/recruitment/v2/applications/me",
)

_TOKEN_PATTERNS = (
    re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._\-]{8,})"),
    re.compile(r"(?i)\b(access[_-]?token|refresh[_-]?token|token|jwt|sessionid|"
               r"phpsessid|laravel_session|xsrf-token)(\s*[:=]\s*\"?)([A-Za-z0-9._\-%]{8,})"),
    re.compile(r"\b(eyJ[A-Za-z0-9._\-]{20,})"),  # bare JWT
)


def redact(value: Any) -> str:
    """Mask anything that looks like a credential. Used on ALL output."""
    text = str(value)
    text = _TOKEN_PATTERNS[0].sub(r"\1 ***REDACTED***", text)
    text = _TOKEN_PATTERNS[1].sub(r"\1\2***REDACTED***", text)
    text = _TOKEN_PATTERNS[2].sub("***REDACTED***", text)
    return text


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").casefold()


def is_allowed(url: str) -> bool:
    host = _host_of(url)
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def _parse_cookie_header(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in raw.split(";"):
        name, _, value = part.strip().partition("=")
        if name and value:
            out[name.strip()] = value.strip()
    return out


@dataclass
class Session:
    """A browser session the user captured themselves."""

    cookies: dict[str, str]
    source: str = "unknown"

    @property
    def token(self) -> str:
        for key in ("accessToken", "access_token", "token", "jwt"):
            if self.cookies.get(key):
                return self.cookies[key]
        return ""

    @property
    def is_empty(self) -> bool:
        return not self.cookies

    @property
    def cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def summary(self) -> dict[str, Any]:
        """Safe-to-display description. Never exposes values."""
        return {
            "source": self.source,
            "cookie_count": len(self.cookies),
            "cookie_names": sorted(self.cookies)[:12],
            "has_access_token": bool(self.token),
            "token_preview": (self.token[:6] + "..." + self.token[-4:]) if self.token else "",
        }

    # ------------------------------------------------------------------ #
    @classmethod
    def from_env(cls) -> "Session":
        raw = os.getenv("MAGANGHUB_COOKIE", "").strip()
        return cls(_parse_cookie_header(raw), source=".env MAGANGHUB_COOKIE") if raw else cls({}, "kosong")

    @classmethod
    def from_file(cls, path: str | Path = SESSION_FILE) -> "Session":
        p = Path(path)
        if not p.exists():
            return cls({}, "kosong")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return cls({}, "kosong")

        # Accept both {"name": "value"} and Playwright's [{name, value}, ...]
        if isinstance(data, list):
            cookies = {c["name"]: c["value"] for c in data
                       if isinstance(c, dict) and c.get("name") and c.get("value")}
        elif isinstance(data, dict):
            inner = data.get("cookies", data)
            cookies = {k: str(v) for k, v in inner.items()} if isinstance(inner, dict) else {}
        else:
            cookies = {}
        return cls(cookies, source=str(p.name))

    @classmethod
    def load(cls) -> "Session":
        """Prefer .env, fall back to session.json."""
        session = cls.from_env()
        return session if not session.is_empty else cls.from_file()

    def save(self, path: str | Path = SESSION_FILE) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.cookies, indent=1), encoding="utf-8")
        try:
            p.chmod(0o600)  # owner read/write only
        except OSError:
            pass
        return p


class SessionClient:
    """Minimal authenticated GET client, locked to Kemnaker domains."""

    def __init__(self, session: Session, timeout: float = 25.0) -> None:
        self.session = session
        self.timeout = timeout

    def _headers(self, url: str) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": f"https://{_host_of(url)}/",
        }
        if self.session.cookie_header:
            headers["Cookie"] = self.session.cookie_header
        if self.session.token:
            headers["Authorization"] = f"Bearer {self.session.token}"
        return headers

    def get_json(self, url: str) -> tuple[bool, Any, str]:
        """Returns (ok, payload, message). `message` is always redacted."""
        if not is_allowed(url):
            return False, None, f"URL ditolak - di luar domain Kemnaker: {url}"
        if self.session.is_empty:
            return False, None, ("Belum ada sesi. Jalankan `magangku session help` "
                                 "untuk cara mengisinya dengan aman.")
        try:
            import httpx
        except ImportError:
            return False, None, "httpx belum terpasang (pip install -r requirements.txt)"

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                resp = client.get(url, headers=self._headers(url))
        except Exception as exc:  # noqa: BLE001
            return False, None, redact(f"{type(exc).__name__}: {exc}")

        if resp.status_code in (301, 302, 303, 307, 308):
            return False, None, ("Dialihkan ke halaman login - sesi sudah kedaluwarsa. "
                                 "Ambil ulang cookie dari browser.")
        if resp.status_code in (401, 403):
            return False, None, f"HTTP {resp.status_code} - sesi tidak valid / kedaluwarsa."
        if resp.status_code != 200:
            return False, None, f"HTTP {resp.status_code}"

        try:
            return True, resp.json(), "ok"
        except json.JSONDecodeError:
            return False, None, ("Respons bukan JSON (kemungkinan halaman HTML login "
                                 "atau challenge Cloudflare).")

    def discover_profile(
        self, endpoints: tuple[str, ...] = PROFILE_ENDPOINTS
    ) -> tuple[Any | None, str, list[str]]:
        """Try each candidate endpoint. Returns (payload, url_used, attempt_log)."""
        log: list[str] = []
        for url in endpoints:
            ok, payload, message = self.get_json(url)
            log.append(f"{'OK ' if ok else '-- '} {url}  ({message})")
            if ok and payload:
                return payload, url, log
        return None, "", log

    def discover_applications(
        self, endpoints: tuple[str, ...] = APPLICATION_ENDPOINTS
    ) -> tuple[Any | None, str, list[str]]:
        """Fetch the user's submitted applications from the new gateway."""
        log: list[str] = []
        for url in endpoints:
            ok, payload, message = self.get_json(url)
            log.append(f"{'OK ' if ok else '-- '} {url}  ({message})")
            if ok and payload is not None:
                return payload, url, log
        return None, "", log

    def probe(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Probe one endpoint and describe what came back, without auth if needed.

        Unlike `get_json` this never short-circuits on a missing session: probing
        anonymously is exactly how we learn which endpoints are public.
        """
        result: dict[str, Any] = {
            "url": url, "status": 0, "ok": False, "shape": "", "note": "",
            "items": 0, "total": 0,
        }
        if not is_allowed(url):
            result["note"] = "ditolak - di luar domain Kemnaker"
            return result
        try:
            import httpx
        except ImportError:
            result["note"] = "httpx belum terpasang"
            return result

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                resp = client.get(url, headers=self._headers(url), params=params or {})
        except Exception as exc:  # noqa: BLE001
            result["note"] = redact(f"{type(exc).__name__}: {exc}")
            return result

        result["status"] = resp.status_code
        if resp.status_code in (301, 302, 303, 307, 308):
            result["note"] = f"redirect -> {redact(resp.headers.get('location', '?'))}"
            return result
        try:
            payload = resp.json()
        except json.JSONDecodeError:
            body = resp.text[:120].replace("\n", " ")
            result["note"] = f"bukan JSON: {redact(body)}"
            return result

        result["ok"] = resp.status_code == 200
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                result["items"] = len(data)
                result["shape"] = "envelope-list"
            elif isinstance(data, dict):
                result["items"] = 1
                result["shape"] = "envelope-object"
            else:
                result["shape"] = "object:" + ",".join(list(payload)[:5])
            meta = payload.get("meta")
            if isinstance(meta, dict):
                pag = meta.get("pagination") if isinstance(meta.get("pagination"), dict) else meta
                result["total"] = pag.get("total", 0) or 0
                if "hostname" in meta:
                    result["note"] = f"pod={meta['hostname']}"
            for key in ("failed", "message", "error", "type"):
                if key in payload and not result["note"]:
                    result["note"] = f"{key}={redact(payload[key])[:70]}"
        elif isinstance(payload, list):
            result["shape"] = "bare-list"
            result["items"] = len(payload)
        return result


# --------------------------------------------------------------------------- #
def capture_via_browser(
    login_url: str = "https://account.kemnaker.go.id/auth/login",
    landing_host: str = "maganghub.kemnaker.go.id",
    timeout_seconds: int = 300,
) -> Session:
    """Open a real browser so the USER logs in themselves, then read cookies.

    The password is typed by the user into the official Kemnaker page. This
    process never sees it - it only reads the resulting session cookies from
    the browser it launched, on the user's own machine.

    Requires: pip install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Fitur ini butuh Playwright:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, timeout=60_000)

        print("\n>> Silakan login SENDIRI di jendela browser yang terbuka.")
        print(">> Password Anda diketik langsung di halaman resmi Kemnaker.")
        print(f">> Menunggu hingga {timeout_seconds} detik...\n")

        try:
            page.wait_for_url(f"**{landing_host}**", timeout=timeout_seconds * 1000)
        except Exception:  # noqa: BLE001
            print("!! Tidak terdeteksi pindah ke MagangHub - cookie diambil apa adanya.")

        cookies = {
            c["name"]: c["value"]
            for c in context.cookies()
            if _host_of("https://" + c.get("domain", "").lstrip(".")) .endswith("kemnaker.go.id")
            or c.get("domain", "").endswith("kemnaker.go.id")
        }
        browser.close()

    return Session(cookies, source="browser (login oleh pengguna)")


HELP_TEXT = """\
Cara menghubungkan MagangKu dengan akun MagangHub Anda - SEMUANYA LOKAL
=======================================================================

MagangKu tidak pernah meminta password Anda. Pilih salah satu:


CARA 1 - Ekspor JSON dari DevTools  [PALING AMAN, SELALU BERHASIL]
-------------------------------------------------------------------
Tidak ada token yang berpindah tangan sama sekali.

  1. Login ke https://maganghub.kemnaker.go.id seperti biasa.
  2. Buka halaman profil / biodata Anda.
  3. Tekan F12 -> tab "Network" -> muat ulang halaman (F5).
  4. Cari permintaan yang mengembalikan data profil Anda
     (biasanya bertipe XHR/fetch, isinya JSON berisi nama & pendidikan Anda).
  5. Klik kanan -> "Copy" -> "Copy response".
  6. Simpan ke berkas, misal `profil.json`, lalu jalankan:

        magangku sync --from-file profil.json

  MagangKu akan memetakan data itu ke profile.yml Anda.


CARA 2 - Tempel cookie sesi  [praktis, token disimpan lokal]
-------------------------------------------------------------
  1. Login ke MagangHub di browser.
  2. F12 -> tab "Application" (Chrome) / "Storage" (Firefox) -> Cookies.
  3. Salin nilai cookie sesi (biasanya `accessToken`).
  4. Masukkan ke berkas .env pada baris:

        MAGANGHUB_COOKIE=accessToken=<nilai-yang-Anda-salin>

  5. Cek koneksinya:

        magangku session status
        magangku sync --auto

  .env sudah masuk .gitignore dan tidak akan pernah ter-commit.


CARA 3 - Login lewat browser yang dibuka MagangKu  [opsional]
--------------------------------------------------------------
  pip install playwright && playwright install chromium
  magangku session capture

  Jendela browser asli terbuka, Anda login sendiri di halaman resmi
  Kemnaker, lalu MagangKu hanya membaca cookie hasilnya.


YANG TIDAK AKAN PERNAH DILAKUKAN MAGANGKU
------------------------------------------
  - Meminta atau menyimpan password Anda
  - Mengirim data Anda ke server mana pun selain kemnaker.go.id
  - Mengirim lamaran tanpa Anda tekan sendiri tombol kirimnya
"""
