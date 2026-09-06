"""Registry of Kemnaker API endpoints, old and new.

BACKGROUND (per Sep 2026)
-------------------------
Kemnaker sedang memigrasikan MagangHub dari backend lama ke API gateway baru:

  LAMA  https://maganghub.kemnaker.go.id/be/v1/api/...     (Laravel, snake_case)
  BARU  https://api.kemnaker.go.id/maganghub/<svc>/v2/...  (gateway, camelCase)

Bukti untuk gateway baru:
  * Respons yang dikirim pengguna dari `/v2/applications/me` memuat
    `meta.hostname = "maganghub-recruitment-…"` — pola nama pod Kubernetes,
    jadi backend-nya memang terpecah per-service (recruitment/vacancy/onboarding).
  * Path terlihat di chunk JS MagangHub (Next.js) dan dicatat oleh
    riizalhp/cuti-new — yang juga melaporkan endpoint LAMA kini membalas
    `UnauthorizedException` untuk publik.
  * Pola gateway yang sama sudah terbukti dipakai KarirHub:
    `https://api.kemnaker.go.id/karirhub/catalogue/v1/industrial-vacancies`
    (rywndr/Lokerbot).

STATUS KEJUJURAN
----------------
Sandbox ini tidak bisa menjangkau kemnaker.go.id (Cloudflare + Alibaba WAF),
jadi endpoint di bawah TIDAK BISA saya verifikasi secara langsung. Tiap entri
diberi label `confidence`:

  confirmed  : bentuk respons sudah terlihat nyata (dari pengguna / proyek lain)
  documented : path tercatat di chunk JS MagangHub, bentuk respons belum terlihat
  guess      : ekstrapolasi pola; kemungkinan besar 404

`magangku probe` mencoba semuanya dari mesin ANDA lalu melaporkan mana yang
hidup — itulah cara kita mengubah "guess" menjadi fakta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

GATEWAY = "https://api.kemnaker.go.id"
LEGACY = "https://maganghub.kemnaker.go.id/be/v1/api"
MONEV = "https://monev.maganghub.kemnaker.go.id/api"


@dataclass(frozen=True)
class Endpoint:
    key: str
    url: str
    method: str = "GET"
    kind: str = "vacancies"          # vacancies | profile | reference | applications
    confidence: str = "guess"        # confirmed | documented | guess
    auth: str = "none"               # none | optional | required
    params: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def build(self, **over: Any) -> tuple[str, dict[str, Any]]:
        params = {**self.params, **{k: v for k, v in over.items() if v not in (None, "")}}
        return self.url, params


# --------------------------------------------------------------------------- #
# Vacancy listing - the core of MagangKu
# --------------------------------------------------------------------------- #
VACANCY_ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(
        key="legacy_vacancies_aktif",
        url=f"{LEGACY}/list/vacancies-aktif",
        confidence="confirmed",
        auth="optional",
        params={"order_by": "jumlah_kuota", "order_direction": "DESC", "limit": 100},
        note="Backend lama. Terbukti bekerja s/d ~Nov 2025; laporan terbaru "
             "menyebut UnauthorizedException untuk akses publik.",
    ),
    Endpoint(
        key="gw_vacancy_v2_vacancies",
        url=f"{GATEWAY}/maganghub/vacancy/v2/vacancies",
        confidence="guess",
        auth="optional",
        params={"page": 1, "limit": 100},
        note="Tebakan pola dari service 'vacancy'. cuti-new melaporkan 404, "
             "tapi mungkin butuh header/param berbeda.",
    ),
    Endpoint(
        key="gw_recruitment_v2_vacancies",
        url=f"{GATEWAY}/maganghub/recruitment/v2/vacancies",
        confidence="guess",
        auth="optional",
        params={"page": 1, "limit": 100},
        note="Service 'recruitment' terbukti ada (hostname pod pada respons "
             "applications/me).",
    ),
    Endpoint(
        key="gw_catalogue_v2_vacancies",
        url=f"{GATEWAY}/maganghub/catalogue/v2/vacancies",
        confidence="guess",
        auth="optional",
        params={"page": 1, "limit": 100},
        note="Meniru pola KarirHub yang sudah terbukti: "
             "karirhub/catalogue/v1/industrial-vacancies.",
    ),
    Endpoint(
        key="gw_catalogue_v1_internship",
        url=f"{GATEWAY}/maganghub/catalogue/v1/internship-vacancies",
        confidence="guess",
        auth="optional",
        params={"page": 1, "limit": 100},
        note="Analogi paling dekat dengan endpoint KarirHub yang hidup.",
    ),
)

# --------------------------------------------------------------------------- #
# Applications / profile - butuh sesi login pengguna
# --------------------------------------------------------------------------- #
APPLICATION_ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(
        key="gw_applications_me",
        url=f"{GATEWAY}/v2/applications/me",
        kind="applications",
        confidence="confirmed",
        auth="required",
        params={"page": 1},
        note="DIKONFIRMASI oleh respons yang dikirim pengguna. Paginasi "
             "Laravel + meta.hostname/client_ip.",
    ),
    Endpoint(
        key="gw_vacancy_applications_me",
        url=f"{GATEWAY}/maganghub/recruitment/v2/vacancies/{{vacancy_id}}/applications/me",
        kind="applications",
        confidence="documented",
        auth="required",
        note="Terlihat di chunk JS MagangHub. Status lamaran untuk satu lowongan.",
    ),
)

PROFILE_ENDPOINTS_V2: tuple[Endpoint, ...] = (
    Endpoint(
        key="gw_profile_v1_me",
        url=f"{GATEWAY}/profile/v1/profiles/me",
        kind="profile",
        confidence="documented",
        auth="required",
        note="Domain 'profile/v1' terkonfirmasi lewat URL foto profil "
             "(api.kemnaker.go.id/profile/v1/profiles/<id>/picture).",
    ),
    Endpoint(
        key="gw_users_me_v2",
        url=f"{GATEWAY}/v2/users/me",
        kind="profile",
        confidence="guess",
        auth="required",
        note="Mengikuti pola /v2/applications/me yang sudah terkonfirmasi.",
    ),
    Endpoint(
        key="monev_users_me",
        url=f"{MONEV}/users/me",
        kind="profile",
        confidence="confirmed",
        auth="required",
        note="Terkonfirmasi dari maganghub-autopresence. Hanya berisi data "
             "peserta yang SUDAH diterima magang.",
    ),
    Endpoint(
        key="legacy_profile",
        url=f"{LEGACY}/profile",
        kind="profile",
        confidence="guess",
        auth="required",
        note="Backend lama.",
    ),
)

REFERENCE_ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(key="gw_onboarding_provinces", url=f"{GATEWAY}/maganghub/onboarding/v2/provinces",
             kind="reference", confidence="documented", note="Terlihat di chunk JS."),
    Endpoint(key="gw_onboarding_cities", url=f"{GATEWAY}/maganghub/onboarding/v2/cities",
             kind="reference", confidence="documented", note="Terlihat di chunk JS."),
    Endpoint(key="gw_onboarding_companies", url=f"{GATEWAY}/maganghub/onboarding/v2/companies/search",
             kind="reference", confidence="documented", note="Terlihat di chunk JS."),
    Endpoint(key="gw_study_programs", url=f"{GATEWAY}/maganghub/vacancy/v2/study-programs",
             kind="reference", confidence="documented", note="Terlihat di chunk JS."),
    Endpoint(key="legacy_provinces", url=f"{LEGACY}/list/provinces",
             kind="reference", confidence="confirmed",
             params={"limit": "all"}, note="Backend lama."),
)

ALL_ENDPOINTS: tuple[Endpoint, ...] = (
    VACANCY_ENDPOINTS + APPLICATION_ENDPOINTS + PROFILE_ENDPOINTS_V2 + REFERENCE_ENDPOINTS
)


def by_kind(kind: str) -> tuple[Endpoint, ...]:
    return tuple(e for e in ALL_ENDPOINTS if e.kind == kind)


def get(key: str) -> Endpoint | None:
    return next((e for e in ALL_ENDPOINTS if e.key == key), None)


CONFIDENCE_LABEL = {
    "confirmed": "terkonfirmasi",
    "documented": "tercatat di JS",
    "guess": "tebakan",
}
