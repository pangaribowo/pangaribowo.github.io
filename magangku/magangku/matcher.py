"""Explainable scoring engine: how well does a vacancy fit the profile?

Design principle: every number the user sees must be traceable. Each component
returns a 0..1 sub-score plus a human-readable reason, and the final score is a
weighted blend rendered as 0..100. No black boxes, no LLM required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import Vacancy
from .profile import (
    JABODETABEK,
    LEVEL_ORDER,
    Profile,
    _norm,
    city_tokens,
    clusters_for,
    level_key,
)


@dataclass
class Component:
    key: str
    score: float          # 0..1
    weight: float         # normalised
    reason: str = ""

    @property
    def contribution(self) -> float:
        return self.score * self.weight


@dataclass
class MatchResult:
    vacancy: Vacancy
    score: float                       # 0..100
    verdict: str                       # strong | good | maybe | weak
    components: list[Component] = field(default_factory=list)
    bonuses: list[tuple[str, float]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.vacancy.to_dict(),
            "score": self.score,
            "verdict": self.verdict,
            "reasons": self.reasons,
            "blockers": self.blockers,
            "components": [
                {
                    "key": c.key,
                    "score": round(c.score, 4),
                    "weight": round(c.weight, 4),
                    "contribution": round(c.contribution * 100, 2),
                    "reason": c.reason,
                }
                for c in self.components
            ],
            "bonuses": [{"label": label, "points": pts} for label, pts in self.bonuses],
        }


# --------------------------------------------------------------------------- #
def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9+#.]{1,}", text.casefold()))


def _skill_hit(skill: str, haystack: str, tokens: set[str]) -> bool:
    """Multi-word skills need a substring match; single words match on token."""
    s = skill.casefold().strip()
    if not s:
        return False
    if " " in s or "-" in s:
        return s in haystack
    return s in tokens


class Matcher:
    """Scores vacancies against one profile."""

    def __init__(self, profile: Profile) -> None:
        self.p = profile
        self.w = profile.normalized_weights

    # ------------------------------------------------------------------ #
    # Hard filters
    # ------------------------------------------------------------------ #
    def blockers_for(self, v: Vacancy) -> list[str]:
        f = self.p.filters or {}
        out: list[str] = []

        if f.get("only_open", True) and not v.is_open:
            out.append(f"Pendaftaran sudah tutup ({v.deadline})")

        min_quota = int(f.get("min_quota") or 0)
        if min_quota and v.quota < min_quota:
            out.append(f"Kuota {v.quota} < minimum {min_quota}")

        max_comp = float(f.get("max_competition") or 0)
        if max_comp and v.competition_ratio > max_comp:
            out.append(f"Persaingan {v.competition_ratio}/slot > batas {max_comp}")

        if f.get("government_only") and not v.is_government:
            out.append("Bukan instansi pemerintah")

        haystack = v.search_text
        for kw in (f.get("exclude_keywords") or []):
            if str(kw).casefold().strip() and str(kw).casefold().strip() in haystack:
                out.append(f"Mengandung kata terlarang: '{kw}'")

        include_prov = [_norm(x) for x in (f.get("include_provinces") or []) if _norm(x)]
        if include_prov and _norm(v.province) not in include_prov:
            out.append(f"Provinsi '{v.province}' di luar include_provinces")

        if not self.p.allow_outside and self._is_outside_preference(v):
            out.append(f"Di luar preferensi lokasi ({v.location}) - allow_outside: false")

        # Age gate, only when the profile declares an age.
        age = (self.p.raw.get("identity") or {}).get("age")
        if age:
            try:
                age_i = int(age)
                if v.age_min and age_i < v.age_min:
                    out.append(f"Usia {age_i} < minimal {v.age_min}")
                if v.age_max and age_i > v.age_max:
                    out.append(f"Usia {age_i} > maksimal {v.age_max}")
            except (TypeError, ValueError):
                pass

        return out

    # ------------------------------------------------------------------ #
    # Components
    # ------------------------------------------------------------------ #
    def _major_score(self, v: Vacancy) -> tuple[float, str]:
        if not v.majors:
            return 0.55, "Lowongan tidak membatasi program studi"
        if not self.p.majors:
            return 0.0, "Profil belum mengisi program studi"

        vac_norm = [_norm(m) for m in v.majors]
        vac_clusters: set[str] = set()
        for m in v.majors:
            vac_clusters |= clusters_for(m)

        # 1. exact / substring match on the declared majors
        for term in self.p.major_terms:
            for vn, original in zip(vac_norm, v.majors):
                if term and (term == vn or term in vn or vn in term):
                    return 1.0, f"Jurusan cocok persis: {original}"

        # 2. cluster overlap (Informatika ~ Ilmu Komputer)
        shared = self.p.major_clusters & vac_clusters
        if shared:
            label = ", ".join(sorted(shared))
            return 0.85, f"Serumpun dengan jurusan Anda ({label})"

        # 3. adjacent majors declared by the user
        for term in self.p.adjacent_terms:
            for vn, original in zip(vac_norm, v.majors):
                if term and (term == vn or term in vn or vn in term):
                    return 0.6, f"Termasuk jurusan alternatif Anda: {original}"

        if self.p.adjacent_clusters & vac_clusters:
            return 0.5, "Serumpun dengan jurusan alternatif Anda"

        return 0.0, f"Jurusan tidak cocok (diminta: {', '.join(v.majors[:3])})"

    def _skill_score(self, v: Vacancy) -> tuple[float, str]:
        if not self.p.skills:
            return 0.0, "Profil belum mengisi skill"
        haystack = v.search_text
        tokens = _tokenize(haystack)

        hits = [s for s in self.p.skills if _skill_hit(s, haystack, tokens)]
        bonus_hits = [s for s in self.p.interests if _skill_hit(s, haystack, tokens)]

        if not hits and not bonus_hits:
            return 0.0, "Tidak ada skill yang disebut di lowongan"

        # Saturating curve: 3 matching skills is already a strong signal.
        base = min(1.0, len(hits) / 3.0)
        base = min(1.0, base + 0.12 * min(len(bonus_hits), 2))

        parts = []
        if hits:
            parts.append("skill cocok: " + ", ".join(hits[:4]))
        if bonus_hits:
            parts.append("minat: " + ", ".join(bonus_hits[:2]))
        return base, "; ".join(parts)

    # Score returned by `_location_score` when a vacancy matches no preference.
    OUTSIDE_LOCATION_SCORE = 0.12

    def _location_score(self, v: Vacancy) -> tuple[float, str]:
        city_terms, prov_terms = self.p.city_terms, self.p.province_terms
        if not city_terms and not prov_terms:
            return 0.5, "Tidak ada preferensi lokasi"

        v_city, v_prov = _norm(v.city), _norm(v.province)
        v_city_expanded = city_tokens(v.city)

        if city_terms and (v_city in city_terms or v_city_expanded & city_terms):
            return 1.0, f"Kota prioritas: {v.city.title()}"
        if prov_terms and (v_prov in prov_terms or any(t in v_prov for t in prov_terms)):
            return 0.72, f"Provinsi preferensi: {v.province.title()}"
        if city_terms & JABODETABEK and v_city in JABODETABEK:
            return 0.65, "Masih di area Jabodetabek"
        return self.OUTSIDE_LOCATION_SCORE, f"Di luar preferensi: {v.location}"

    def _is_outside_preference(self, v: Vacancy) -> bool:
        """True when the vacancy matches none of the user's preferred places."""
        if not (self.p.city_terms or self.p.province_terms):
            return False
        return self._location_score(v)[0] <= self.OUTSIDE_LOCATION_SCORE

    def _opportunity_score(self, v: Vacancy) -> tuple[float, str]:
        if v.quota <= 0:
            return 0.1, "Kuota tidak diinformasikan"
        ratio = v.competition_ratio
        if ratio <= 1:
            score = 1.0
        elif ratio <= 3:
            score = 0.85
        elif ratio <= 6:
            score = 0.65
        elif ratio <= 12:
            score = 0.42
        elif ratio <= 25:
            score = 0.22
        else:
            score = 0.08
        pct = round(v.acceptance_estimate * 100)
        return score, f"{v.registered} pelamar / {v.quota} kuota ({ratio}:1, est. {pct}%)"

    def _level_score(self, v: Vacancy) -> tuple[float, str]:
        if not v.levels:
            return 0.7, "Jenjang tidak dibatasi"
        mine = self.p.level_key
        if not mine:
            return 0.5, "Jenjang profil belum diisi"

        wanted = {level_key(x) for x in v.levels} - {""}
        if not wanted:
            return 0.6, "Jenjang lowongan tidak terbaca"
        if mine in wanted:
            return 1.0, f"Jenjang sesuai: {', '.join(v.levels)}"

        try:
            mine_idx = LEVEL_ORDER.index(mine)
            best = min(LEVEL_ORDER.index(w) for w in wanted if w in LEVEL_ORDER)
        except (ValueError, IndexError):
            return 0.3, f"Jenjang diminta: {', '.join(v.levels)}"

        if mine_idx > best:
            return 0.55, f"Jenjang Anda di atas syarat ({', '.join(v.levels)})"
        return 0.0, f"Jenjang belum memenuhi ({', '.join(v.levels)})"

    def _urgency_score(self, v: Vacancy) -> tuple[float, str]:
        left = v.days_left
        if left is None:
            return 0.5, "Batas pendaftaran tidak diketahui"
        if left < 0:
            return 0.0, f"Tutup {abs(left)} hari lalu"
        if left <= 3:
            return 1.0, f"Tutup dalam {left} hari - segera!"
        if left <= 7:
            return 0.85, f"Sisa {left} hari"
        if left <= 21:
            return 0.6, f"Sisa {left} hari"
        return 0.4, f"Masih lama ({left} hari)"

    # ------------------------------------------------------------------ #
    def score(self, v: Vacancy) -> MatchResult:
        specs = [
            ("major", self._major_score),
            ("skills", self._skill_score),
            ("location", self._location_score),
            ("opportunity", self._opportunity_score),
            ("level", self._level_score),
            ("urgency", self._urgency_score),
        ]

        components: list[Component] = []
        for key, fn in specs:
            raw, reason = fn(v)
            components.append(
                Component(key=key, score=max(0.0, min(1.0, raw)),
                          weight=self.w.get(key, 0.0), reason=reason)
            )

        base = sum(c.contribution for c in components) * 100.0

        # Additive bonuses (raw points on the 0-100 scale).
        bonuses: list[tuple[str, float]] = []
        boosts = self.p.boosts or {}
        haystack = v.search_text

        for kw, pts in (boosts.get("keywords") or {}).items():
            if str(kw).casefold() in haystack:
                try:
                    bonuses.append((f"kata kunci '{kw}'", float(pts)))
                except (TypeError, ValueError):
                    continue

        for company, pts in (boosts.get("companies") or {}).items():
            if _norm(company) and _norm(company) in _norm(v.company):
                try:
                    bonuses.append((f"perusahaan favorit ({company})", float(pts)))
                except (TypeError, ValueError):
                    continue

        gov_bonus = boosts.get("government_bonus")
        if gov_bonus and v.is_government:
            try:
                bonuses.append(("instansi pemerintah", float(gov_bonus)))
            except (TypeError, ValueError):
                pass

        total = base + sum(pts for _, pts in bonuses)
        total = round(max(0.0, min(100.0, total)), 1)

        blockers = self.blockers_for(v)
        if blockers:
            total = 0.0

        reasons = [
            f"{c.reason} (+{c.contribution * 100:.1f})"
            for c in sorted(components, key=lambda c: -c.contribution)
            if c.reason and c.contribution > 0.01
        ]
        reasons += [f"{label} (+{pts})" for label, pts in bonuses]

        return MatchResult(
            vacancy=v,
            score=total,
            verdict="blocked" if blockers else self.p.verdict(total),
            components=components,
            bonuses=bonuses,
            reasons=reasons,
            blockers=blockers,
        )

    def rank(
        self,
        vacancies: list[Vacancy],
        *,
        include_blocked: bool = False,
        min_score: float = 0.0,
        limit: int | None = None,
    ) -> list[MatchResult]:
        results = [self.score(v) for v in vacancies]
        if not include_blocked:
            results = [r for r in results if r.passed]
        if min_score > 0:
            results = [r for r in results if r.score >= min_score]
        results.sort(key=lambda r: (-r.score, r.vacancy.days_left
                                    if r.vacancy.days_left is not None else 999))
        return results[:limit] if limit else results
