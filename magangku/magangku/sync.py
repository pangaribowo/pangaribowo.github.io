"""Map a Kemnaker/SIAPkerja profile payload onto MagangKu's profile.yml.

The upstream shape is not publicly documented and differs between SIAPkerja,
MagangHub and Monev. So instead of hard-coding one schema, this module walks
the payload and looks for *any* of the field names those services are known to
use (Indonesian and English). That makes the import work across variants and
degrade gracefully when a field is missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

from .profile import LEVEL_ALIASES

# --------------------------------------------------------------------------- #
# Field-name candidates, ordered by how specific/reliable they are.
# --------------------------------------------------------------------------- #
NAME_KEYS = ("nama_lengkap", "full_name", "fullname", "nama", "name")
EMAIL_KEYS = ("email", "surel", "email_address")
PHONE_KEYS = ("no_hp", "nomor_hp", "no_telepon", "telepon", "phone_number",
              "phone", "handphone", "msisdn")
CITY_KEYS = ("nama_kabupaten", "kabupaten", "kota", "domisili", "city",
             "regency_name", "nama_kota", "alamat_kota")
PROVINCE_KEYS = ("nama_provinsi", "nama_propinsi", "provinsi", "propinsi", "province")
ADDRESS_KEYS = ("alamat", "alamat_lengkap", "address", "street_address")

EDU_LIST_KEYS = ("pendidikan", "riwayat_pendidikan", "educations", "education",
                 "data_pendidikan", "pendidikan_terakhir")
EDU_LEVEL_KEYS = ("jenjang", "jenjang_pendidikan", "tingkat", "level",
                  "education_level", "strata")
EDU_MAJOR_KEYS = ("program_studi", "prodi", "jurusan", "major", "study_program",
                  "bidang_studi", "nama_jurusan")
EDU_SCHOOL_KEYS = ("institusi", "nama_institusi", "nama_sekolah", "sekolah",
                   "universitas", "perguruan_tinggi", "kampus", "school",
                   "university", "institution", "nama_kampus")
GPA_KEYS = ("ipk", "gpa", "nilai_ipk", "indeks_prestasi")

SKILL_LIST_KEYS = ("keahlian", "skills", "skill", "kompetensi", "keterampilan",
                   "data_keahlian", "kemampuan")
SKILL_NAME_KEYS = ("nama_keahlian", "nama", "title", "name", "skill_name",
                   "keahlian", "kompetensi")

# Levels ordered weakest -> strongest, for "highest education wins".
_LEVEL_RANK = {"sma": 1, "d3": 2, "d4": 3, "s1": 4, "s2": 5, "s3": 6}
_LEVEL_PRETTY = {"sma": "SMA/SMK sederajat", "d3": "Diploma III",
                 "d4": "Diploma IV", "s1": "Sarjana", "s2": "Magister",
                 "s3": "Doktor"}


def _unwrap(payload: Any) -> Any:
    """Peel common envelopes: {"data": {...}}, {"result": {...}}."""
    seen = 0
    while isinstance(payload, dict) and seen < 4:
        for key in ("data", "result", "payload", "user", "profile", "profil"):
            inner = payload.get(key)
            if isinstance(inner, (dict, list)) and inner:
                payload = inner
                break
        else:
            break
        seen += 1
    return payload


def _walk(node: Any, depth: int = 0):
    """Yield every dict in the payload, breadth-ish, depth-capped."""
    if depth > 6:
        return
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value, depth + 1)
    elif isinstance(node, list):
        for item in node[:50]:
            yield from _walk(item, depth + 1)


def _find(payload: Any, keys: Iterable[str]) -> Any:
    """First non-empty scalar value for any of `keys`, searched depth-first."""
    wanted = [k.casefold() for k in keys]
    for want in wanted:  # honour candidate priority over document order
        for node in _walk(payload):
            for key, value in node.items():
                if key.casefold() != want:
                    continue
                if isinstance(value, (str, int, float)) and str(value).strip():
                    text = str(value).strip()
                    if text.casefold() not in {"null", "none", "-"}:
                        return text
    return ""


def _find_list(payload: Any, keys: Iterable[str]) -> list[Any]:
    wanted = {k.casefold() for k in keys}
    for node in _walk(payload):
        for key, value in node.items():
            if key.casefold() in wanted and isinstance(value, list) and value:
                return value
    return []


def _level_key(text: str) -> str:
    low = str(text).casefold()
    for key, tokens in LEVEL_ALIASES.items():
        if any(token in low for token in tokens):
            return key
    return ""


def _skill_names(raw: list[Any]) -> list[str]:
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            for key in SKILL_NAME_KEYS:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    out.append(value.strip())
                    break
    seen: set[str] = set()
    uniq: list[str] = []
    for value in out:
        low = value.casefold()
        if low not in seen and len(value) <= 60:
            seen.add(low)
            uniq.append(value)
    return uniq


# --------------------------------------------------------------------------- #
def map_kemnaker_profile(payload: Any) -> dict[str, Any]:
    """Extract what MagangKu needs from a Kemnaker profile payload."""
    root = _unwrap(payload)

    identity: dict[str, str] = {
        "name": _find(root, NAME_KEYS),
        "email": _find(root, EMAIL_KEYS),
        "phone": _find(root, PHONE_KEYS),
        "city": _find(root, CITY_KEYS),
    }

    # ---- education: pick the highest level present ---------------------- #
    best: dict[str, Any] = {}
    best_rank = -1
    for entry in _find_list(root, EDU_LIST_KEYS):
        if not isinstance(entry, dict):
            continue
        level = _level_key(_find(entry, EDU_LEVEL_KEYS))
        rank = _LEVEL_RANK.get(level, 0)
        if rank >= best_rank:
            best_rank, best = rank, entry

    majors: list[str] = []
    if best:
        identity["level"] = _LEVEL_PRETTY.get(
            _level_key(_find(best, EDU_LEVEL_KEYS)), _find(best, EDU_LEVEL_KEYS))
        identity["university"] = _find(best, EDU_SCHOOL_KEYS)
        identity["gpa"] = _find(best, GPA_KEYS)
        major = _find(best, EDU_MAJOR_KEYS)
        if major:
            majors.append(major)
    else:
        # Flat payloads: fields sit at the top level, no education array.
        level = _level_key(_find(root, EDU_LEVEL_KEYS))
        if level:
            identity["level"] = _LEVEL_PRETTY.get(level, "")
        identity["university"] = _find(root, EDU_SCHOOL_KEYS)
        identity["gpa"] = _find(root, GPA_KEYS)
        major = _find(root, EDU_MAJOR_KEYS)
        if major:
            majors.append(major)

    skills = _skill_names(_find_list(root, SKILL_LIST_KEYS))

    province = _find(root, PROVINCE_KEYS)
    identity = {k: v for k, v in identity.items() if v}

    return {
        "identity": identity,
        "majors": majors,
        "skills": skills,
        "location": {
            "cities": [identity["city"]] if identity.get("city") else [],
            "provinces": [province] if province else [],
        },
        "_found": {
            "identity_fields": sorted(identity),
            "majors": len(majors),
            "skills": len(skills),
            "province": province or "",
        },
    }


def apply_to_profile(base: dict[str, Any], mapped: dict[str, Any],
                     *, overwrite: bool = False) -> tuple[dict[str, Any], list[str]]:
    """Merge mapped data into an existing profile dict.

    Returns (new_profile, changes). Existing user values are preserved unless
    `overwrite=True` - the official data is a *suggestion*, not a mandate.
    """
    from .cv import TEMPLATE_VALUES

    out = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
           for k, v in base.items()}
    changes: list[str] = []

    identity = dict(out.get("identity") or {})
    for key, value in (mapped.get("identity") or {}).items():
        current = str(identity.get(key, "")).strip()
        if overwrite or not current or current.casefold() in TEMPLATE_VALUES:
            if current != value:
                changes.append(f"identity.{key}: '{current or '(kosong)'}' -> '{value}'")
                identity[key] = value
    out["identity"] = identity

    for key in ("majors", "skills"):
        incoming = mapped.get(key) or []
        if not incoming:
            continue
        existing = list(out.get(key) or [])
        if overwrite:
            if existing != incoming:
                changes.append(f"{key}: diganti dengan {len(incoming)} entri dari MagangHub")
            out[key] = incoming
        else:
            seen = {str(x).casefold() for x in existing}
            added = [x for x in incoming if str(x).casefold() not in seen]
            if added:
                changes.append(f"{key}: +{len(added)} baru ({', '.join(added[:5])})")
                out[key] = existing + added

    loc_in = mapped.get("location") or {}
    location = dict(out.get("location") or {})
    for key in ("cities", "provinces"):
        incoming = loc_in.get(key) or []
        if not incoming:
            continue
        existing = list(location.get(key) or [])
        seen = {str(x).casefold() for x in existing}
        added = [x for x in incoming if str(x).casefold() not in seen]
        if added:
            changes.append(f"location.{key}: +{', '.join(added)}")
            location[key] = existing + added
    location.setdefault("allow_outside", True)
    out["location"] = location

    return out, changes


def load_profile_dict(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def write_profile_dict(path: str | Path, data: dict[str, Any]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=88),
        encoding="utf-8",
    )
    return p
