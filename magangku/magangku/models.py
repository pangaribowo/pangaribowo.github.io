"""Domain model for a MagangHub (Kemnaker) internship vacancy.

The upstream API returns a deeply nested, inconsistently typed payload
(JSON-encoded strings inside JSON, nulls everywhere). `Vacancy` is the clean,
flat representation the rest of the system works with.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Any

APPLY_URL_TMPL = "https://maganghub.kemnaker.go.id/magang-nasional/lowongan/{id}"


def _iso(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "-"}:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[: len(fmt) + 2].strip(), fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


@dataclass
class Vacancy:
    """A single internship position, normalised."""

    id: str
    position: str = ""
    description: str = ""
    requirements: str = ""

    company: str = ""
    company_id: str = ""
    logo: str = ""
    address: str = ""
    city: str = ""
    city_code: str = ""
    province: str = ""
    province_code: str = ""

    quota: int = 0
    registered: int = 0

    majors: list[str] = field(default_factory=list)
    levels: list[str] = field(default_factory=list)

    gov_agency: str = ""
    sub_gov_agency: str = ""

    batch: str = ""
    year: str = ""
    placement: str = ""
    status: str = ""

    age_min: int | None = None
    age_max: int | None = None

    deadline: date | None = None
    start_date: date | None = None
    end_date: date | None = None

    scraped_at: str = ""

    # ------------------------------------------------------------------ #
    # Derived values
    # ------------------------------------------------------------------ #
    @property
    def apply_url(self) -> str:
        return APPLY_URL_TMPL.format(id=self.id)

    @property
    def is_government(self) -> bool:
        return bool(self.gov_agency or self.sub_gov_agency)

    @property
    def competition_ratio(self) -> float:
        """Applicants per available slot. Higher = harder."""
        if self.quota <= 0:
            return float(self.registered) if self.registered else 0.0
        return round(self.registered / self.quota, 2)

    @property
    def acceptance_estimate(self) -> float:
        """Naive probability of getting a slot, in 0..1."""
        if self.quota <= 0:
            return 0.0
        return round(min(1.0, self.quota / (self.registered + 1)), 4)

    @property
    def days_left(self) -> int | None:
        if not self.deadline:
            return None
        return (self.deadline - date.today()).days

    @property
    def is_open(self) -> bool:
        left = self.days_left
        return True if left is None else left >= 0

    @property
    def location(self) -> str:
        parts = [p for p in (self.city.title() if self.city else "", self.province.title() if self.province else "") if p]
        return ", ".join(parts) or "Tidak disebutkan"

    @property
    def search_text(self) -> str:
        return " ".join(
            filter(
                None,
                [
                    self.position,
                    self.description,
                    self.requirements,
                    self.company,
                    self.placement,
                    " ".join(self.majors),
                    " ".join(self.levels),
                    self.gov_agency,
                    self.sub_gov_agency,
                    self.city,
                    self.province,
                ],
            )
        ).lower()

    # ------------------------------------------------------------------ #
    # Serialisation
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        data = {k: _iso(v) for k, v in asdict(self).items()}
        data.update(
            {
                "apply_url": self.apply_url,
                "competition_ratio": self.competition_ratio,
                "acceptance_estimate": self.acceptance_estimate,
                "days_left": self.days_left,
                "is_open": self.is_open,
                "is_government": self.is_government,
                "location": self.location,
            }
        )
        return data

    def to_json(self) -> str:
        base = {k: _iso(v) for k, v in asdict(self).items()}
        return json.dumps(base, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Vacancy":
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in allowed}
        for key in ("deadline", "start_date", "end_date"):
            if key in clean:
                clean[key] = _parse_date(clean[key])
        for key in ("quota", "registered"):
            if key in clean and clean[key] is not None:
                try:
                    clean[key] = int(clean[key])
                except (TypeError, ValueError):
                    clean[key] = 0
        for key in ("majors", "levels"):
            value = clean.get(key)
            if isinstance(value, str):
                try:
                    clean[key] = json.loads(value)
                except json.JSONDecodeError:
                    clean[key] = [v.strip() for v in value.split(",") if v.strip()]
            elif value is None:
                clean[key] = []
        return cls(**clean)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
