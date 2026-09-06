"""Turn raw Kemnaker MagangHub API payloads into `Vacancy` objects.

Upstream quirks handled here:
  * `program_studi` is a JSON *string* containing a list of `{id, title}`
  * `jenjang` is a JSON *string* containing a list of plain strings
  * nested objects (`perusahaan`, `jadwal`, `government_agency`) may be null
  * dates arrive as `"YYYY-MM-DD HH:MM:SS"` or null
  * numeric fields sometimes arrive as strings
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from .models import Vacancy, _parse_date

_WS = re.compile(r"[ \t\r\f\v]+")
_MULTI_NL = re.compile(r"\n{3,}")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = _WS.sub(" ", text)
    text = _MULTI_NL.sub("\n\n", text)
    return text.strip()


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _maybe_json_list(value: Any) -> list[Any]:
    """`program_studi` / `jenjang` are JSON strings. Decode defensively."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"null", "[]"}:
            return []
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return [p.strip() for p in text.split(",") if p.strip()]
        if isinstance(decoded, list):
            return decoded
        return [decoded]
    return [value]


def _titles(items: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            title = item.get("title") or item.get("nama") or item.get("name")
            if title:
                out.append(str(title).strip())
        elif item:
            out.append(str(item).strip())
    # de-duplicate, preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for value in out:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            uniq.append(value)
    return uniq


def _sub(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def normalize_vacancy(raw: dict[str, Any], scraped_at: str = "") -> Vacancy | None:
    """Map one raw API record onto a `Vacancy`. Returns None when unusable."""
    if not isinstance(raw, dict):
        return None

    vacancy_id = raw.get("id_posisi") or raw.get("id") or raw.get("uuid")
    if not vacancy_id:
        return None

    company = _sub(raw, "perusahaan")
    schedule = _sub(raw, "jadwal")
    gov = _sub(raw, "government_agency")
    sub_gov = _sub(raw, "sub_government_agency")
    status_ref = _sub(raw, "ref_status_posisi")

    return Vacancy(
        id=str(vacancy_id),
        position=_clean_text(raw.get("posisi") or raw.get("positionName")),
        description=_clean_text(raw.get("deskripsi_posisi")),
        requirements=_clean_text(raw.get("syarat_khusus")),
        company=_clean_text(company.get("nama_perusahaan")),
        company_id=str(company.get("id_perusahaan") or ""),
        logo=str(company.get("logo") or ""),
        address=_clean_text(company.get("alamat")),
        city=_clean_text(company.get("nama_kabupaten")),
        city_code=str(company.get("kode_kabupaten") or ""),
        province=_clean_text(company.get("nama_provinsi")),
        province_code=str(company.get("kode_provinsi") or ""),
        quota=_as_int(raw.get("jumlah_kuota")),
        registered=_as_int(raw.get("jumlah_terdaftar")),
        majors=_titles(_maybe_json_list(raw.get("program_studi"))),
        levels=_titles(_maybe_json_list(raw.get("jenjang"))),
        gov_agency=_clean_text(gov.get("government_agency_name")),
        sub_gov_agency=_clean_text(sub_gov.get("sub_government_agency_name")),
        batch=str(schedule.get("angkatan") or ""),
        year=str(schedule.get("tahun") or ""),
        placement=_clean_text(raw.get("penempatan")),
        status=_clean_text(status_ref.get("nama_status_posisi")),
        age_min=_as_int(raw.get("usia_minimal"), 0) or None,
        age_max=_as_int(raw.get("usia_maksimal"), 0) or None,
        deadline=_parse_date(schedule.get("tanggal_batas_pendaftaran")
                             or schedule.get("tanggal_pendaftaran_akhir")),
        start_date=_parse_date(schedule.get("tanggal_mulai")),
        end_date=_parse_date(schedule.get("tanggal_selesai")),
        scraped_at=scraped_at,
    )


def normalize_payload(payload: Any, scraped_at: str = "") -> list[Vacancy]:
    """Accept a full API page (`{"data": [...]}`) or a bare list."""
    if isinstance(payload, dict):
        rows = payload.get("data")
        scraped_at = scraped_at or str(payload.get("_scraped_at") or "")
    else:
        rows = payload
    if not isinstance(rows, list):
        return []
    out: list[Vacancy] = []
    for row in rows:
        vacancy = normalize_vacancy(row, scraped_at=scraped_at)
        if vacancy is not None:
            out.append(vacancy)
    return out


def page_total(payload: Any) -> int:
    if isinstance(payload, dict):
        meta = payload.get("meta") or {}
        pagination = meta.get("pagination") or {}
        return _as_int(pagination.get("total"))
    return 0


def last_page(payload: Any) -> int:
    if isinstance(payload, dict):
        meta = payload.get("meta") or {}
        pagination = meta.get("pagination") or {}
        return _as_int(pagination.get("last_page"))
    return 0
