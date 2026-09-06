"""Load, validate and reason about the user's applicant profile."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# --------------------------------------------------------------------------- #
# Domain knowledge: Indonesian study-programme synonyms.
# Keys are canonical clusters; values are tokens that imply the cluster.
# Used so "Informatika" in a profile still matches "Ilmu Komputer" upstream.
# --------------------------------------------------------------------------- #
MAJOR_CLUSTERS: dict[str, set[str]] = {
    "informatika": {
        "informatika", "ilmu komputer", "computer science", "teknik informatika",
        "sistem informasi", "information system", "teknologi informasi",
        "rekayasa perangkat lunak", "software engineering", "teknik komputer",
        "manajemen informatika", "ilmu komputasi", "komputer",
    },
    "data": {
        "data science", "sains data", "statistika", "statistik", "matematika",
        "aktuaria", "data analyst", "big data", "analisis data",
    },
    "elektro": {
        "teknik elektro", "elektronika", "teknik listrik", "mekatronika",
        "teknik telekomunikasi", "instrumentasi", "electrical",
    },
    "mesin": {"teknik mesin", "teknik industri", "manufaktur", "otomotif", "mechanical"},
    "sipil": {"teknik sipil", "arsitektur", "perencanaan wilayah", "planologi", "bangunan"},
    "ekonomi": {
        "ekonomi", "manajemen", "akuntansi", "keuangan", "perbankan", "bisnis",
        "administrasi bisnis", "ekonomi pembangunan", "manajemen bisnis",
    },
    "hukum": {"hukum", "ilmu hukum", "law", "syariah"},
    "komunikasi": {
        "komunikasi", "ilmu komunikasi", "hubungan masyarakat", "humas",
        "jurnalistik", "public relations", "broadcasting", "periklanan",
    },
    "sosial": {
        "sosiologi", "ilmu politik", "administrasi publik", "administrasi negara",
        "hubungan internasional", "kesejahteraan sosial", "antropologi",
        "ilmu pemerintahan", "kebijakan publik",
    },
    "psikologi": {"psikologi", "psychology", "bimbingan konseling"},
    "kesehatan": {
        "kesehatan masyarakat", "keperawatan", "kebidanan", "farmasi",
        "gizi", "kedokteran", "analis kesehatan", "rekam medis", "kesehatan",
    },
    "pendidikan": {"pendidikan", "keguruan", "pgsd", "pg paud", "tarbiyah"},
    "pertanian": {
        "pertanian", "agribisnis", "agroteknologi", "kehutanan", "peternakan",
        "perikanan", "teknologi pangan", "budidaya",
    },
    "desain": {
        "desain", "dkv", "desain komunikasi visual", "multimedia", "seni rupa",
        "animasi", "desain produk", "desain interior",
    },
    "pariwisata": {"pariwisata", "perhotelan", "tata boga", "hospitality", "kuliner"},
    "kimia": {"teknik kimia", "kimia", "teknologi pengolahan", "polimer", "karet dan plastik"},
    "lingkungan": {"teknik lingkungan", "kesehatan lingkungan", "geografi", "geologi", "tambang"},
}

LEVEL_ALIASES: dict[str, set[str]] = {
    "sma": {"sma", "smk", "sma/smk", "sma/smk sederajat", "slta", "sederajat"},
    "d3": {"d3", "diploma iii", "diploma 3", "diploma tiga", "ahli madya"},
    "d4": {"d4", "diploma iv", "diploma 4", "sarjana terapan"},
    "s1": {"s1", "sarjana", "strata 1", "bachelor", "strata satu"},
    "s2": {"s2", "magister", "master", "strata 2", "pascasarjana"},
    "s3": {"s3", "doktor", "doctoral", "phd"},
}

# Regency/city groupings so "Yogyakarta" matches the whole metro area.
CITY_ALIASES: dict[str, set[str]] = {
    "yogyakarta": {"yogyakarta", "jogja", "jogjakarta", "sleman", "bantul", "diy"},
    "jakarta": {
        "jakarta", "jakarta pusat", "jakarta selatan", "jakarta barat",
        "jakarta timur", "jakarta utara", "dki",
    },
    "bandung": {"bandung", "cimahi"},
    "surabaya": {"surabaya", "sidoarjo", "gresik"},
    "semarang": {"semarang", "demak", "kendal"},
    "solo": {"surakarta", "solo", "sukoharjo", "karanganyar", "boyolali", "klaten"},
    "medan": {"medan", "deli serdang"},
    "makassar": {"makassar", "maros", "gowa"},
}

JABODETABEK = {
    "jakarta", "bogor", "depok", "tangerang", "tangerang selatan", "bekasi",
}


def _norm(text: Any) -> str:
    text = str(text or "").casefold().strip()
    text = re.sub(r"\b(kota|kab\.?|kabupaten|adm\.?|administrasi)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value)]


def clusters_for(text: str) -> set[str]:
    """Which canonical major-clusters does this free text belong to?"""
    norm = _norm(text)
    if not norm:
        return set()
    found = {name for name, tokens in MAJOR_CLUSTERS.items()
             if any(token in norm for token in tokens)}
    return found


def level_key(text: str) -> str:
    norm = _norm(text)
    for key, tokens in LEVEL_ALIASES.items():
        if any(re.search(rf"\b{re.escape(t)}\b", norm) for t in tokens):
            return key
    return ""


LEVEL_ORDER = ["sma", "d3", "d4", "s1", "s2", "s3"]


def city_tokens(name: str) -> set[str]:
    """Expand a city name into itself plus its metro-area aliases."""
    norm = _norm(name)
    if not norm:
        return set()
    tokens = {norm}
    for _, members in CITY_ALIASES.items():
        if norm in members or any(m in norm for m in members):
            tokens |= members
    return tokens


# --------------------------------------------------------------------------- #
@dataclass
class Profile:
    raw: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    # identity
    name: str = ""
    email: str = ""
    phone: str = ""
    home_city: str = ""
    university: str = ""
    level: str = ""
    gpa: str = ""

    majors: list[str] = field(default_factory=list)
    adjacent_majors: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)

    pref_cities: list[str] = field(default_factory=list)
    pref_provinces: list[str] = field(default_factory=list)
    allow_outside: bool = True

    filters: dict[str, Any] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    boosts: dict[str, Any] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    letter: dict[str, Any] = field(default_factory=dict)
    notify: dict[str, Any] = field(default_factory=dict)

    DEFAULT_WEIGHTS = {
        "major": 0.30, "skills": 0.22, "location": 0.18,
        "opportunity": 0.15, "level": 0.10, "urgency": 0.05,
    }
    DEFAULT_THRESHOLDS = {"strong": 75.0, "good": 60.0, "maybe": 45.0}

    # ----------------------------------------------------------------- #
    @classmethod
    def load(cls, path: str | Path) -> "Profile":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(
                f"Profil tidak ditemukan: {p}\n"
                f"Jalankan: cp profile.example.yml profile.yml"
            )
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.from_dict(data, path=p)

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: Path | None = None) -> "Profile":
        identity = data.get("identity") or {}
        location = data.get("location") or {}

        weights = dict(cls.DEFAULT_WEIGHTS)
        for key, value in (data.get("weights") or {}).items():
            try:
                weights[key] = float(value)
            except (TypeError, ValueError):
                continue

        thresholds = dict(cls.DEFAULT_THRESHOLDS)
        for key, value in (data.get("thresholds") or {}).items():
            try:
                thresholds[key] = float(value)
            except (TypeError, ValueError):
                continue

        return cls(
            raw=data,
            path=path,
            name=str(identity.get("name") or "").strip(),
            email=str(identity.get("email") or "").strip(),
            phone=str(identity.get("phone") or "").strip(),
            home_city=str(identity.get("city") or "").strip(),
            university=str(identity.get("university") or "").strip(),
            level=str(identity.get("level") or "").strip(),
            gpa=str(identity.get("gpa") or "").strip(),
            majors=_as_list(data.get("majors")),
            adjacent_majors=_as_list(data.get("adjacent_majors")),
            skills=[s.casefold() for s in _as_list(data.get("skills"))],
            interests=[s.casefold() for s in _as_list(data.get("interests"))],
            pref_cities=_as_list(location.get("cities")),
            pref_provinces=_as_list(location.get("provinces")),
            allow_outside=bool(location.get("allow_outside", True)),
            filters=data.get("filters") or {},
            weights=weights,
            boosts=data.get("boosts") or {},
            thresholds=thresholds,
            letter=data.get("letter") or {},
            notify=data.get("notify") or {},
        )

    # ----------------------------------------------------------------- #
    # Cached derived sets
    # ----------------------------------------------------------------- #
    @property
    def major_clusters(self) -> set[str]:
        out: set[str] = set()
        for m in self.majors:
            out |= clusters_for(m)
        return out

    @property
    def adjacent_clusters(self) -> set[str]:
        out: set[str] = set()
        for m in self.adjacent_majors:
            out |= clusters_for(m)
        return out - self.major_clusters

    @property
    def major_terms(self) -> set[str]:
        return {_norm(m) for m in self.majors if _norm(m)}

    @property
    def adjacent_terms(self) -> set[str]:
        return {_norm(m) for m in self.adjacent_majors if _norm(m)}

    @property
    def level_key(self) -> str:
        return level_key(self.level)

    @property
    def city_terms(self) -> set[str]:
        out: set[str] = set()
        for c in self.pref_cities:
            out |= city_tokens(c)
        return out

    @property
    def province_terms(self) -> set[str]:
        return {_norm(p) for p in self.pref_provinces if _norm(p)}

    @property
    def normalized_weights(self) -> dict[str, float]:
        total = sum(max(0.0, v) for v in self.weights.values())
        if total <= 0:
            return dict(self.DEFAULT_WEIGHTS)
        return {k: max(0.0, v) / total for k, v in self.weights.items()}

    def verdict(self, score: float) -> str:
        t = self.thresholds
        if score >= t.get("strong", 75):
            return "strong"
        if score >= t.get("good", 60):
            return "good"
        if score >= t.get("maybe", 45):
            return "maybe"
        return "weak"

    # ----------------------------------------------------------------- #
    def validate(self) -> list[str]:
        """Return a list of human-readable warnings (empty = healthy)."""
        warnings: list[str] = []
        if not self.name:
            warnings.append("identity.name kosong - surat lamaran akan terasa generik.")
        if not self.majors:
            warnings.append("majors kosong - skor kecocokan jurusan selalu 0.")
        elif not self.major_clusters:
            warnings.append(
                f"majors {self.majors} tidak dikenali kamus internal; "
                "pencocokan akan mengandalkan teks mentah saja."
            )
        if not self.skills:
            warnings.append("skills kosong - komponen skill tidak akan berkontribusi.")
        if not self.level:
            warnings.append("identity.level kosong - filter jenjang dilewati.")
        elif not self.level_key:
            warnings.append(f"identity.level '{self.level}' tidak dikenali.")
        if not (self.pref_cities or self.pref_provinces):
            warnings.append("Preferensi lokasi kosong - semua lokasi dianggap netral.")
        return warnings

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name or "(belum diisi)",
            "level": self.level or "-",
            "majors": self.majors,
            "clusters": sorted(self.major_clusters),
            "skills": len(self.skills),
            "cities": self.pref_cities,
            "provinces": self.pref_provinces,
            "weights": self.normalized_weights,
            "path": str(self.path) if self.path else "(inline)",
        }


def default_profile_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.getenv("MAGANGKU_PROFILE")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parent.parent
    local = root / "profile.yml"
    return local if local.exists() else root / "profile.example.yml"
