"""End-to-end tests for the MagangKu pipeline.

Run: pytest -q
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from magangku.cv import extract_skills, merge_into_profile, parse_cv
from magangku.letter import build_checklist, build_letter
from magangku.matcher import Matcher
from magangku.models import Vacancy
from magangku.normalize import normalize_payload, normalize_vacancy
from magangku.profile import Profile, clusters_for, level_key
from magangku.report import export_all
from magangku.scraper import load_fixtures
from magangku.storage import Store

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def _raw(**over):
    base = {
        "id_posisi": "abc-123",
        "posisi": "Fullstack Developer",
        "deskripsi_posisi": "Membangun aplikasi web dengan React dan Python.",
        "syarat_khusus": None,
        "jumlah_kuota": 5,
        "jumlah_terdaftar": 10,
        "program_studi": '[{"id":"1","title":"Teknik Informatika"}]',
        "jenjang": '["Sarjana"]',
        "perusahaan": {
            "id_perusahaan": "co-1",
            "nama_perusahaan": "PT Contoh",
            "alamat": "Jl. Mawar 1",
            "nama_kabupaten": "KOTA YOGYAKARTA",
            "kode_kabupaten": "3471",
            "nama_provinsi": "DAERAH ISTIMEWA YOGYAKARTA",
            "kode_provinsi": "34",
            "logo": "x.png",
        },
        "jadwal": {
            "tanggal_batas_pendaftaran": (date.today() + timedelta(days=20)).isoformat() + " 00:00:00",
            "angkatan": "2",
            "tahun": "2026",
        },
        "government_agency": {"government_agency_name": None},
        "sub_government_agency": {"sub_government_agency_name": None},
        "ref_status_posisi": {"nama_status_posisi": "Terverifikasi"},
    }
    base.update(over)
    return base


@pytest.fixture
def profile() -> Profile:
    return Profile.from_dict({
        "identity": {"name": "Uji Coba", "email": "uji@test.id",
                     "level": "Sarjana", "city": "Yogyakarta"},
        "majors": ["Teknik Informatika"],
        "skills": ["python", "react", "sql"],
        "location": {"cities": ["Yogyakarta"], "provinces": ["DAERAH ISTIMEWA YOGYAKARTA"],
                     "allow_outside": True},
        "filters": {"only_open": True, "min_quota": 1},
    })


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
def test_normalize_decodes_nested_json_strings():
    v = normalize_vacancy(_raw())
    assert v is not None
    assert v.majors == ["Teknik Informatika"]   # was a JSON string
    assert v.levels == ["Sarjana"]              # was a JSON string
    assert v.city == "KOTA YOGYAKARTA"
    assert v.quota == 5 and v.registered == 10


def test_normalize_survives_nulls_and_missing_blocks():
    v = normalize_vacancy({"id_posisi": "x", "posisi": "Tanpa Relasi"})
    assert v is not None
    assert v.company == "" and v.majors == [] and v.deadline is None
    assert v.competition_ratio == 0.0


def test_normalize_rejects_record_without_id():
    assert normalize_vacancy({"posisi": "tanpa id"}) is None


def test_normalize_strips_html():
    v = normalize_vacancy(_raw(deskripsi_posisi="<p>Halo<br/>dunia</p>&nbsp;&amp; lagi"))
    assert "<" not in v.description and "&nbsp;" not in v.description
    assert "Halo" in v.description and "&" in v.description


def test_derived_metrics():
    v = normalize_vacancy(_raw(jumlah_kuota=4, jumlah_terdaftar=19))
    assert v.competition_ratio == 4.75
    assert v.acceptance_estimate == 0.2
    assert v.is_open is True


def test_zero_quota_never_divides_by_zero():
    v = normalize_vacancy(_raw(jumlah_kuota=0, jumlah_terdaftar=7))
    assert v.acceptance_estimate == 0.0
    assert v.competition_ratio == 7.0


# --------------------------------------------------------------------------- #
# Profile knowledge
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,cluster", [
    ("Teknik Informatika", "informatika"),
    ("Ilmu Komputer", "informatika"),
    ("Sistem Informasi", "informatika"),
    ("Statistika", "data"),
    ("Ilmu Hukum", "hukum"),
    ("Kesehatan Masyarakat", "kesehatan"),
])
def test_major_clusters(text, cluster):
    assert cluster in clusters_for(text)


@pytest.mark.parametrize("text,key", [
    ("Sarjana", "s1"), ("S1", "s1"), ("Diploma III", "d3"),
    ("Magister", "s2"), ("SMA/SMK sederajat", "sma"),
])
def test_level_aliases(text, key):
    assert level_key(text) == key


def test_profile_validate_flags_gaps():
    warnings = Profile.from_dict({"identity": {}}).validate()
    assert any("majors" in w for w in warnings)
    assert any("skills" in w for w in warnings)


def test_weights_normalise_to_one(profile):
    assert sum(profile.normalized_weights.values()) == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
def test_exact_major_and_city_scores_high(profile):
    result = Matcher(profile).score(normalize_vacancy(_raw()))
    assert result.score > 70
    assert result.verdict in {"strong", "good"}
    assert result.passed


def test_cluster_match_beats_unrelated_major(profile):
    m = Matcher(profile)
    related = m.score(normalize_vacancy(
        _raw(program_studi='[{"id":"1","title":"Ilmu Komputer"}]')))
    unrelated = m.score(normalize_vacancy(
        _raw(program_studi='[{"id":"1","title":"Kebidanan"}]')))
    assert related.score > unrelated.score


def test_closed_vacancy_is_blocked(profile):
    past = (date.today() - timedelta(days=5)).isoformat() + " 00:00:00"
    v = normalize_vacancy(_raw(jadwal={"tanggal_batas_pendaftaran": past}))
    result = Matcher(profile).score(v)
    assert not result.passed
    assert result.score == 0.0
    assert any("tutup" in b.lower() for b in result.blockers)


def test_exclude_keyword_blocks(profile):
    profile.filters = {"only_open": True, "exclude_keywords": ["fullstack"]}
    result = Matcher(profile).score(normalize_vacancy(_raw()))
    assert not result.passed


def test_allow_outside_false_blocks_other_cities(profile):
    profile.allow_outside = False
    far = _raw()
    far["perusahaan"] = {**far["perusahaan"], "nama_kabupaten": "KOTA MEDAN",
                         "nama_provinsi": "SUMATERA UTARA"}
    assert not Matcher(profile).score(normalize_vacancy(far)).passed


def test_components_sum_to_score(profile):
    result = Matcher(profile).score(normalize_vacancy(_raw()))
    expected = sum(c.contribution for c in result.components) * 100
    assert result.score == pytest.approx(expected, abs=0.15)


def test_every_component_has_a_reason(profile):
    result = Matcher(profile).score(normalize_vacancy(_raw()))
    assert len(result.components) == 6
    assert all(c.reason for c in result.components)


def test_rank_sorts_descending_and_limits(profile):
    ranked = Matcher(profile).rank(load_fixtures(), limit=5)
    assert len(ranked) <= 5
    assert [r.score for r in ranked] == sorted((r.score for r in ranked), reverse=True)


def test_boost_keyword_raises_score(profile):
    plain = Matcher(profile).score(normalize_vacancy(_raw()))
    profile.boosts = {"keywords": {"react": 5}}
    boosted = Matcher(profile).score(normalize_vacancy(_raw()))
    assert boosted.score > plain.score


def test_score_is_bounded(profile):
    profile.boosts = {"keywords": {"react": 999}}
    assert Matcher(profile).score(normalize_vacancy(_raw())).score <= 100.0


# --------------------------------------------------------------------------- #
# Fixtures / data
# --------------------------------------------------------------------------- #
def test_fixtures_load_and_are_usable():
    vacancies = load_fixtures()
    assert len(vacancies) >= 100
    assert all(isinstance(v, Vacancy) and v.id for v in vacancies)
    assert any(v.is_open for v in vacancies), "demo butuh lowongan yang masih buka"


def test_fixture_pages_have_expected_envelope():
    for path in (ROOT / "data" / "fixtures").glob("vacancies_*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "data" in payload and isinstance(payload["data"], list)
        assert normalize_payload(payload)


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
def test_store_detects_new_and_changed(tmp_path):
    store = Store(tmp_path / "t.db")
    v = normalize_vacancy(_raw())

    first = store.upsert_many([v])
    assert first["new"] == ["abc-123"]

    second = store.upsert_many([v])
    assert second["new"] == [] and second["changed"] == []

    v2 = normalize_vacancy(_raw(jumlah_terdaftar=40))
    third = store.upsert_many([v2])
    assert third["changed"][0]["registered_after"] == 40
    assert len(store.trend("abc-123")) == 3


def test_store_roundtrip_preserves_fields(tmp_path):
    store = Store(tmp_path / "t.db")
    store.upsert_many([normalize_vacancy(_raw())])
    got = store.get("abc-123")
    assert got.position == "Fullstack Developer"
    assert got.majors == ["Teknik Informatika"]
    assert got.deadline is not None


def test_tracker_status_lifecycle(tmp_path):
    store = Store(tmp_path / "t.db")
    store.upsert_many([normalize_vacancy(_raw())])
    store.track("abc-123", status="shortlisted")
    store.track("abc-123", status="applied")
    assert store.application_status("abc-123") == "applied"
    assert len(store.applications()) == 1
    with pytest.raises(ValueError):
        store.track("abc-123", status="tidak-valid")


# --------------------------------------------------------------------------- #
# CV parsing
# --------------------------------------------------------------------------- #
CV_TEXT = """Budi Santoso
Yogyakarta
budi@mail.com | 081234567890
Universitas Gadjah Mada dengan IPK 3.75
Sarjana Teknik Informatika
Keahlian: Python, JavaScript, SQL, Docker, Figma
"""


def test_parse_cv_extracts_core_fields(tmp_path):
    p = tmp_path / "cv.txt"
    p.write_text(CV_TEXT, encoding="utf-8")
    parsed = parse_cv(p)
    ident = parsed["identity"]
    assert ident["name"] == "Budi Santoso"
    assert ident["email"] == "budi@mail.com"
    assert ident["gpa"] == "3.75"
    assert ident["level"] == "Sarjana"
    assert ident["university"] == "Universitas Gadjah Mada"  # stopword trimmed
    assert "python" in parsed["skills"]


def test_parse_cv_rejects_pdf(tmp_path):
    p = tmp_path / "cv.pdf"
    p.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError, match="pdftotext"):
        parse_cv(p)


def test_extract_skills_avoids_substring_false_positives():
    # "R" and "Go" must not match inside ordinary words.
    assert "go" not in extract_skills("Saya suka bekerja dengan orang lain.")


def test_merge_does_not_overwrite_user_values():
    base = {"identity": {"name": "Nama Asli"}, "skills": ["kotlin"]}
    merged = merge_into_profile(base, {"identity": {"name": "Dari CV"},
                                       "skills": ["python"]})
    assert merged["identity"]["name"] == "Nama Asli"
    assert set(merged["skills"]) == {"kotlin", "python"}


def test_merge_replaces_template_placeholders():
    base = {"identity": {"name": "Nama Lengkap Anda", "email": "email@contoh.com"}}
    merged = merge_into_profile(base, {"identity": {"name": "Budi", "email": "b@x.id"}})
    assert merged["identity"]["name"] == "Budi"


# --------------------------------------------------------------------------- #
# Letter & reports
# --------------------------------------------------------------------------- #
def test_letter_mentions_vacancy_and_profile(profile):
    result = Matcher(profile).score(normalize_vacancy(_raw()))
    letter = build_letter(profile, result)
    assert "Fullstack Developer" in letter
    assert "PT Contoh" in letter
    assert profile.name in letter
    assert "{" not in letter and "None" not in letter


def test_letter_english_variant(profile):
    result = Matcher(profile).score(normalize_vacancy(_raw()))
    letter = build_letter(profile, result, language="en")
    assert "Dear Hiring Team" in letter


def test_letter_handles_empty_description(profile):
    result = Matcher(profile).score(normalize_vacancy(_raw(deskripsi_posisi=None)))
    assert profile.name in build_letter(profile, result)


def test_checklist_contains_apply_link(profile):
    result = Matcher(profile).score(normalize_vacancy(_raw()))
    checklist = build_checklist(profile, result)
    assert "maganghub.kemnaker.go.id" in checklist
    assert "- [ ]" in checklist


def test_export_all_formats(tmp_path, profile):
    results = Matcher(profile).rank(load_fixtures(), limit=8)
    paths = export_all(results, tmp_path, profile)
    assert set(paths) == {"csv", "json", "markdown", "html"}
    for path in paths.values():
        assert path.exists() and path.stat().st_size > 0
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["count"] == len(results)
    assert "<html" in paths["html"].read_text(encoding="utf-8").lower()


def test_html_report_escapes_markup(tmp_path, profile):
    nasty = _raw(posisi='<script>alert(1)</script>')
    result = Matcher(profile).score(normalize_vacancy(nasty))
    from magangku.report import to_html
    html = to_html([result], tmp_path / "r.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html


# --------------------------------------------------------------------------- #
# Session security (modul session.py)
# --------------------------------------------------------------------------- #
from magangku.session import Session, is_allowed, redact  # noqa: E402
from magangku.sync import apply_to_profile, map_kemnaker_profile  # noqa: E402


@pytest.mark.parametrize("raw", [
    "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abcdefghijklmnop",
    "accessToken=eyJhbGciOiJIUzI1NiJ9abcdefghij",
    'token: "supersecretvalue12345"',
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
])
def test_redact_masks_credentials(raw):
    out = redact(raw)
    assert "REDACTED" in out
    assert "eyJhbGciOiJIUzI1NiJ9.abcdefghijklmnop" not in out
    assert "supersecretvalue12345" not in out


def test_redact_leaves_ordinary_text_alone():
    assert redact("tidak ada rahasia di sini") == "tidak ada rahasia di sini"


@pytest.mark.parametrize("url,allowed", [
    ("https://maganghub.kemnaker.go.id/be/v1/api/x", True),
    ("https://monev.maganghub.kemnaker.go.id/api/users/me", True),
    ("https://account.kemnaker.go.id/api/users/me", True),
    ("https://evil.com/steal", False),
    ("https://kemnaker.go.id.evil.com/x", False),
    ("http://localhost:9000/x", False),
])
def test_only_kemnaker_domains_allowed(url, allowed):
    assert is_allowed(url) is allowed


def test_session_summary_never_leaks_full_token():
    s = Session({"accessToken": "abcdefghijklmnopqrstuvwxyz123456"}, "test")
    summary = s.summary()
    assert "abcdefghijklmnopqrstuvwxyz123456" not in json.dumps(summary)
    assert summary["has_access_token"] is True


def test_session_file_is_owner_only(tmp_path):
    path = Session({"accessToken": "x" * 20}, "test").save(tmp_path / "s.json")
    assert oct(path.stat().st_mode)[-3:] == "600"


def test_session_reads_playwright_cookie_array(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps([{"name": "accessToken", "value": "tok123456"},
                             {"name": "other", "value": "v"}]), encoding="utf-8")
    s = Session.from_file(p)
    assert s.token == "tok123456" and len(s.cookies) == 2


def test_empty_session_client_refuses_politely():
    from magangku.session import SessionClient

    ok_, payload, msg = SessionClient(Session({}, "kosong")).get_json(
        "https://maganghub.kemnaker.go.id/be/v1/api/profile")
    assert ok_ is False and payload is None and "sesi" in msg.casefold()


def test_session_client_blocks_foreign_host():
    from magangku.session import SessionClient

    ok_, _, msg = SessionClient(Session({"a": "b"}, "t")).get_json("https://evil.com/x")
    assert ok_ is False and "ditolak" in msg.casefold()


# --------------------------------------------------------------------------- #
# Kemnaker profile sync (modul sync.py)
# --------------------------------------------------------------------------- #
NESTED = {
    "data": {
        "nama_lengkap": "Bowo P", "email": "b@x.id", "no_hp": "0812000",
        "nama_kabupaten": "KOTA YOGYAKARTA", "nama_provinsi": "DAERAH ISTIMEWA YOGYAKARTA",
        "pendidikan": [
            {"jenjang": "SMA", "nama_sekolah": "SMAN 1", "program_studi": "IPA"},
            {"jenjang": "Sarjana", "nama_institusi": "UGM",
             "program_studi": "Teknik Informatika", "ipk": "3.62"},
        ],
        "keahlian": [{"nama_keahlian": "Python"}, {"nama_keahlian": "SQL"}],
    }
}
FLAT = {
    "name": "Siti", "email": "s@x.id", "kota": "Kab. Sleman",
    "jenjang_pendidikan": "Diploma III", "kampus": "Polines",
    "jurusan": "Akuntansi", "gpa": "3.40", "skills": ["Excel", "SAP"],
}


def test_sync_picks_highest_education():
    mapped = map_kemnaker_profile(NESTED)
    assert mapped["identity"]["level"] == "Sarjana"        # not SMA
    assert mapped["identity"]["university"] == "UGM"
    assert mapped["majors"] == ["Teknik Informatika"]
    assert mapped["identity"]["gpa"] == "3.62"


def test_sync_handles_flat_payload():
    mapped = map_kemnaker_profile(FLAT)
    assert mapped["identity"]["level"] == "Diploma III"
    assert mapped["majors"] == ["Akuntansi"]
    assert set(mapped["skills"]) == {"Excel", "SAP"}


def test_sync_survives_unknown_payload():
    mapped = map_kemnaker_profile({"totally": {"unrelated": [1, 2, 3]}})
    assert mapped["identity"] == {} and mapped["majors"] == [] and mapped["skills"] == []


def test_sync_preserves_user_values_by_default():
    base = {"identity": {"name": "Nama Saya Sendiri"}, "skills": ["kotlin"]}
    out, changes = apply_to_profile(base, map_kemnaker_profile(NESTED))
    assert out["identity"]["name"] == "Nama Saya Sendiri"
    assert "kotlin" in out["skills"] and "Python" in out["skills"]
    assert any("skills" in c for c in changes)


def test_sync_overwrite_flag_replaces():
    base = {"identity": {"name": "Lama"}, "skills": ["kotlin"]}
    out, _ = apply_to_profile(base, map_kemnaker_profile(NESTED), overwrite=True)
    assert out["identity"]["name"] == "Bowo P"
    assert out["skills"] == ["Python", "SQL"]


def test_sync_result_is_loadable_as_profile():
    base = yaml_safe(ROOT / "profile.example.yml")
    out, _ = apply_to_profile(base, map_kemnaker_profile(NESTED))
    profile = Profile.from_dict(out)
    assert profile.name == "Nama Lengkap Anda" or profile.name  # merge kept a name
    assert profile.normalized_weights


def yaml_safe(path):
    import yaml as _y
    return _y.safe_load(Path(path).read_text(encoding="utf-8")) or {}


# --------------------------------------------------------------------------- #
# Web API
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(tmp_path, monkeypatch):
    from starlette.testclient import TestClient

    from magangku.web import create_app

    monkeypatch.setenv("MAGANGKU_DB", str(tmp_path / "web.db"))
    monkeypatch.setenv("MAGANGKU_SOURCE", "fixtures")
    monkeypatch.setenv("MAGANGKU_PROFILE", str(ROOT / "profile.example.yml"))
    return TestClient(create_app())


def test_bootstrap_flags_example_profile(client):
    d = client.get("/api/bootstrap").json()
    assert d["ready"] and d["using_example"] and d["needs_onboarding"]


def test_matches_endpoint_filters(client):
    all_ = client.get("/api/matches?limit=500").json()
    high = client.get("/api/matches?min_score=75&limit=500").json()
    assert all_["count"] > 0
    assert high["count"] <= all_["count"]
    assert all(r["score"] >= 75 for r in high["results"])


def test_vacancy_detail_includes_letter(client):
    vid = client.get("/api/matches?limit=1").json()["results"][0]["id"]
    d = client.get(f"/api/vacancy/{vid}").json()
    assert d["letter"] and d["checklist"] and len(d["components"]) == 6


def test_track_roundtrip(client):
    vid = client.get("/api/matches?limit=1").json()["results"][0]["id"]
    assert client.post(f"/api/track/{vid}?status=applied").json()["ok"]
    apps = client.get("/api/applications").json()["applications"]
    assert any(a["vacancy_id"] == vid and a["status"] == "applied" for a in apps)


def test_track_rejects_bad_status(client):
    vid = client.get("/api/matches?limit=1").json()["results"][0]["id"]
    assert client.post(f"/api/track/{vid}?status=nonsense").status_code == 400


def test_sync_endpoint_dry_run_changes_nothing(client):
    d = client.post("/api/sync", json={"json": NESTED, "dry_run": True}).json()
    assert d["applied"] is False and d["found"]["majors"] == 1


def test_sync_endpoint_rejects_unrecognised_payload(client):
    r = client.post("/api/sync", json={"json": {"foo": "bar"}})
    assert r.status_code == 422


def test_sync_endpoint_rejects_bad_json_string(client):
    assert client.post("/api/sync", json={"json": "{not json"}).status_code == 400


def test_session_endpoint_reports_disconnected(client, monkeypatch):
    monkeypatch.delenv("MAGANGHUB_COOKIE", raising=False)
    d = client.get("/api/session").json()
    assert "help" in d and "password" in d["help"].casefold()


def test_export_endpoints(client):
    assert "text/csv" in client.get("/api/export/csv").headers["content-type"]
    assert client.get("/api/export/json").json()["count"] >= 0
    assert "<html" in client.get("/api/export/html").text.lower()
    assert client.get("/api/export/bogus").status_code == 404


def test_cv_endpoint_parses_without_applying(client):
    d = client.post("/api/profile/from-cv",
                    json={"text": CV_TEXT, "apply": False}).json()
    assert d["parsed"]["identity"]["name"] == "Budi Santoso"
    assert d["applied"] is False


def test_cv_endpoint_rejects_short_text(client):
    assert client.post("/api/profile/from-cv", json={"text": "hai"}).status_code == 400
