"""FastAPI dashboard - the primary interface for MagangKu.

Everything the CLI can do, minus the terminal: onboarding, profile editing,
importing your official Kemnaker profile, scraping, scoring, cover letters and
application tracking.

Single-file front end (HTML+CSS+JS inlined): no build step, no CDN, works fully
offline, and safe to open over a preview proxy.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .letter import build_checklist, build_letter
from .matcher import Matcher
from .models import Vacancy
from .profile import Profile, default_profile_path
from .scraper import MagangHubScraper, ScrapeError, load_fixtures, load_provinces
from .session import HELP_TEXT, PROFILE_ENDPOINTS, Session, SessionClient, redact
from .storage import VALID_STATUSES, Store
from .sync import (
    apply_to_profile,
    load_profile_dict,
    map_kemnaker_profile,
    write_profile_dict,
)

ROOT = Path(__file__).resolve().parent.parent


def _profile_path() -> Path:
    return default_profile_path(os.getenv("MAGANGKU_PROFILE"))


def _store() -> Store:
    return Store(os.getenv("MAGANGKU_DB") or ROOT / "magangku.db")


def _load_state() -> tuple[Profile, Store, list[Vacancy]]:
    profile = Profile.load(_profile_path())
    store = _store()
    source = os.getenv("MAGANGKU_SOURCE", "db")
    vacancies = load_fixtures() if source == "fixtures" else (store.all_vacancies() or load_fixtures())
    return profile, store, vacancies


def create_app() -> FastAPI:
    app = FastAPI(title="MagangKu Dashboard", docs_url="/api/docs")

    # ------------------------------------------------------------------ #
    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE

    @app.get("/api/bootstrap")
    def bootstrap() -> dict[str, Any]:
        """Everything the UI needs on first paint, in one round-trip."""
        path = _profile_path()
        is_example = path.name == "profile.example.yml"
        try:
            profile = Profile.load(path)
            warnings = profile.validate()
            summary = profile.summary()
        except Exception as exc:  # noqa: BLE001
            return {"ready": False, "error": str(exc), "needs_onboarding": True}

        store = _store()
        stats = store.stats()
        session = Session.load()

        # Onboarding is needed when the profile is still the shipped example
        # or has no real personalisation yet.
        needs_onboarding = is_example or not profile.majors or not profile.name

        return {
            "ready": True,
            "needs_onboarding": needs_onboarding,
            "using_example": is_example,
            "profile": summary,
            "warnings": warnings,
            "stats": stats,
            "session": session.summary() if not session.is_empty else None,
            "provinces_ref": load_provinces()[:40],
            "source": os.getenv("MAGANGKU_SOURCE", "db"),
        }

    # ---------------------------- profile ----------------------------- #
    @app.get("/api/profile/raw")
    def profile_raw() -> dict[str, Any]:
        path = _profile_path()
        return {"path": str(path), "yaml": path.read_text(encoding="utf-8")}

    @app.post("/api/profile/save")
    def profile_save(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        """Save the structured form back into profile.yml (merging, not clobbering)."""
        import yaml

        target = ROOT / "profile.yml"
        base = load_profile_dict(target) or load_profile_dict(ROOT / "profile.example.yml")

        form = payload.get("form") or {}
        identity = dict(base.get("identity") or {})
        for key in ("name", "email", "phone", "city", "university", "level", "gpa"):
            if key in form:
                identity[key] = form[key]
        base["identity"] = identity

        def _split(value: Any) -> list[str]:
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            return [v.strip() for v in str(value or "").split(",") if v.strip()]

        if "majors" in form:
            base["majors"] = _split(form["majors"])
        if "adjacent_majors" in form:
            base["adjacent_majors"] = _split(form["adjacent_majors"])
        if "skills" in form:
            base["skills"] = _split(form["skills"])

        location = dict(base.get("location") or {})
        if "cities" in form:
            location["cities"] = _split(form["cities"])
        if "provinces" in form:
            location["provinces"] = _split(form["provinces"])
        if "allow_outside" in form:
            location["allow_outside"] = bool(form["allow_outside"])
        base["location"] = location

        filters = dict(base.get("filters") or {})
        for key in ("only_open", "government_only"):
            if key in form:
                filters[key] = bool(form[key])
        for key in ("min_quota", "max_competition"):
            if key in form:
                try:
                    filters[key] = float(form[key])
                except (TypeError, ValueError):
                    pass
        if "exclude_keywords" in form:
            filters["exclude_keywords"] = _split(form["exclude_keywords"])
        base["filters"] = filters

        weights = dict(base.get("weights") or {})
        for key, value in (payload.get("weights") or {}).items():
            try:
                weights[key] = float(value)
            except (TypeError, ValueError):
                continue
        if weights:
            base["weights"] = weights

        write_profile_dict(target, base)
        os.environ["MAGANGKU_PROFILE"] = str(target)
        return JSONResponse({"ok": True, "path": str(target)})

    @app.post("/api/profile/raw")
    def profile_raw_save(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        import yaml

        text = payload.get("yaml", "")
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise HTTPException(400, f"YAML tidak valid: {exc}") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(400, "YAML harus berupa objek/mapping.")
        target = ROOT / "profile.yml"
        target.write_text(text, encoding="utf-8")
        os.environ["MAGANGKU_PROFILE"] = str(target)
        return JSONResponse({"ok": True})

    @app.post("/api/profile/from-cv")
    def profile_from_cv(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Parse CV text pasted straight into the browser."""
        from .cv import (
            extract_city,
            extract_level,
            extract_majors,
            extract_name,
            extract_skills,
            merge_into_profile,
            EMAIL_RE,
            GPA_RE,
            PHONE_RE,
            UNIVERSITY_RE,
            _clean_university,
        )

        text = str(payload.get("text") or "")
        if len(text.strip()) < 30:
            raise HTTPException(400, "Teks CV terlalu pendek.")

        email = EMAIL_RE.search(text)
        phone = PHONE_RE.search(text)
        gpa = GPA_RE.search(text)
        uni = UNIVERSITY_RE.search(text)
        majors = extract_majors(text)
        parsed = {
            "identity": {
                "name": extract_name(text),
                "email": email.group(0) if email else "",
                "phone": phone.group(0) if phone else "",
                "city": extract_city(text),
                "university": _clean_university(uni.group(1)) if uni else "",
                "level": extract_level(text),
                "gpa": gpa.group(1).replace(",", ".") if gpa else "",
            },
            "majors": majors[:2],
            "adjacent_majors": majors[2:4],
            "skills": extract_skills(text),
        }

        if payload.get("apply"):
            target = ROOT / "profile.yml"
            base = load_profile_dict(target)
            seeding = not target.exists()
            if seeding:
                base = load_profile_dict(ROOT / "profile.example.yml")
            merged = merge_into_profile(base, parsed, overwrite_identity=seeding)
            write_profile_dict(target, merged)
            os.environ["MAGANGKU_PROFILE"] = str(target)
        return {"parsed": parsed, "applied": bool(payload.get("apply"))}

    # ------------------------- session & sync -------------------------- #
    @app.get("/api/session")
    def session_status() -> dict[str, Any]:
        session = Session.load()
        return {
            "connected": not session.is_empty,
            "summary": session.summary() if not session.is_empty else None,
            "help": HELP_TEXT,
            "endpoints": list(PROFILE_ENDPOINTS),
        }

    @app.post("/api/session/test")
    def session_test() -> dict[str, Any]:
        session = Session.load()
        if session.is_empty:
            return {"ok": False, "log": [], "message": "Belum ada sesi tersimpan."}
        _, url, log = SessionClient(session).discover_profile()
        return {"ok": bool(url), "endpoint": url, "log": [redact(x) for x in log]}

    @app.post("/api/probe")
    def probe_endpoints(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        """Test every known Kemnaker endpoint from this machine.

        Kemnaker migrated MagangHub to a new API gateway, so which endpoints
        are alive depends on the network you run from. This reports reality
        rather than assumptions.
        """
        from .endpoints import ALL_ENDPOINTS, CONFIDENCE_LABEL

        session = Session.load()
        client = SessionClient(session, timeout=float(payload.get("timeout", 12)))
        kind = payload.get("kind") or ""

        results, alive = [], 0
        for endpoint in ALL_ENDPOINTS:
            if kind and endpoint.kind != kind:
                continue
            if "{vacancy_id}" in endpoint.url:
                continue
            url, params = endpoint.build()
            row = client.probe(url, params)
            row["kind"] = endpoint.kind
            row["confidence"] = endpoint.confidence
            row["confidence_label"] = CONFIDENCE_LABEL.get(endpoint.confidence, "")
            row["auth"] = endpoint.auth
            row["note_static"] = endpoint.note
            row["url"] = redact(row["url"])
            row["note"] = redact(row.get("note", ""))
            alive += 1 if row["ok"] else 0
            results.append(row)
        return {"results": results, "alive": alive, "total": len(results),
                "has_session": not session.is_empty}

    @app.post("/api/sync")
    def sync_profile(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Import an official Kemnaker profile - from pasted JSON or live session."""
        raw = payload.get("json")
        data: Any = None

        if raw:
            if isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise HTTPException(400, f"JSON tidak valid: {exc}") from exc
            else:
                data = raw
            origin = "tempel JSON"
        else:
            session = Session.load()
            if session.is_empty:
                raise HTTPException(400, "Belum ada sesi. Tempel JSON profil Anda, "
                                         "atau isi MAGANGHUB_COOKIE di .env.")
            data, origin, _ = SessionClient(session).discover_profile()
            if data is None:
                raise HTTPException(
                    502,
                    "Tidak ada endpoint profil yang bisa diakses. "
                    "Gunakan cara tempel JSON (lihat panduan).",
                )

        mapped = map_kemnaker_profile(data)
        found = mapped["_found"]
        if not any([found["identity_fields"], found["majors"], found["skills"]]):
            raise HTTPException(
                422,
                "Tidak ada field profil yang dikenali. Pastikan JSON yang ditempel "
                "adalah respons data profil (memuat nama & pendidikan Anda).",
            )

        target = ROOT / "profile.yml"
        base = load_profile_dict(target) or load_profile_dict(ROOT / "profile.example.yml")
        updated, changes = apply_to_profile(base, mapped,
                                            overwrite=bool(payload.get("overwrite")))

        if payload.get("dry_run"):
            return {"found": found, "changes": changes, "applied": False}

        if target.exists():
            target.with_suffix(".yml.bak").write_text(
                target.read_text(encoding="utf-8"), encoding="utf-8")
        write_profile_dict(target, updated)
        os.environ["MAGANGKU_PROFILE"] = str(target)
        return {"found": found, "changes": changes, "applied": True, "origin": origin}

    # ---------------------------- data --------------------------------- #
    @app.post("/api/refresh")
    def refresh(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        """Pull fresh vacancies. Falls back to fixtures when the network blocks us."""
        source = payload.get("source") or "live"
        store = _store()
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")

        if source == "fixtures":
            vacancies = load_fixtures()
            note = "Memakai data contoh offline."
        else:
            try:
                vacancies = MagangHubScraper(delay=float(payload.get("delay", 1.0))).scrape(
                    limit=int(payload.get("limit", 100)),
                    max_pages=payload.get("max_pages"),
                    province=payload.get("province") or None,
                )
                note = "Data langsung dari MagangHub Kemnaker."
            except ScrapeError as exc:
                return {"ok": False, "error": str(exc).splitlines()[0],
                        "hint": "Cloudflare kemungkinan memblokir jaringan ini. "
                                "Coba dari koneksi rumah, atau pakai data contoh."}

        result = store.upsert_many(vacancies)
        store.record_run(source, len(vacancies), len(result["new"]), started)
        return {
            "ok": True, "note": note, "total": len(vacancies),
            "new": len(result["new"]), "changed": len(result["changed"]),
        }

    @app.get("/api/stats")
    def api_stats() -> dict[str, Any]:
        _, store, vacancies = _load_state()
        stats = store.stats()
        stats["loaded"] = len(vacancies)
        return stats

    @app.get("/api/matches")
    def api_matches(
        q: str = "",
        min_score: float = 0.0,
        verdict: str = "",
        province: str = "",
        gov: str = "",
        tracked: str = "",
        limit: int = 200,
    ) -> dict[str, Any]:
        profile, store, vacancies = _load_state()
        results = Matcher(profile).rank(vacancies, min_score=min_score)

        needle = q.casefold().strip()
        items: list[dict[str, Any]] = []
        for r in results:
            v = r.vacancy
            if needle and needle not in v.search_text:
                continue
            if verdict and r.verdict != verdict:
                continue
            if province and province.casefold() not in v.province.casefold():
                continue
            if gov == "1" and not v.is_government:
                continue
            if gov == "0" and v.is_government:
                continue
            status = store.application_status(v.id)
            if tracked == "1" and not status:
                continue
            if tracked == "0" and status:
                continue
            row = r.to_dict()
            row["tracked_status"] = status
            items.append(row)
            if len(items) >= limit:
                break

        return {
            "count": len(items),
            "total_scored": len(results),
            "results": items,
            "provinces": sorted({v.province.title() for v in vacancies if v.province}),
        }

    @app.get("/api/vacancy/{vacancy_id}")
    def api_vacancy(vacancy_id: str) -> dict[str, Any]:
        profile, store, vacancies = _load_state()
        match = next((v for v in vacancies if v.id == vacancy_id), None) or store.get(vacancy_id)
        if not match:
            raise HTTPException(404, "Lowongan tidak ditemukan")
        result = Matcher(profile).score(match)
        return {
            **result.to_dict(),
            "letter": build_letter(profile, result),
            "checklist": build_checklist(profile, result),
            "trend": store.trend(vacancy_id),
            "tracked_status": store.application_status(vacancy_id),
        }

    @app.post("/api/track/{vacancy_id}")
    def api_track(vacancy_id: str, status: str = "shortlisted") -> JSONResponse:
        if status not in VALID_STATUSES:
            raise HTTPException(400, f"Status tidak valid: {', '.join(VALID_STATUSES)}")
        store = _store()
        store.track(vacancy_id, status=status)
        return JSONResponse({"ok": True, "status": status})

    @app.get("/api/applications")
    def api_applications() -> dict[str, Any]:
        return {"applications": _store().applications(),
                "statuses": list(VALID_STATUSES)}

    @app.get("/api/export/{kind}")
    def api_export(kind: str) -> Any:
        from .report import to_csv, to_html, to_json, to_markdown

        if kind not in {"csv", "json", "md", "html"}:
            raise HTTPException(404, "Format tidak dikenal")
        profile, _, vacancies = _load_state()
        results = Matcher(profile).rank(vacancies)
        out = ROOT / "out"
        out.mkdir(exist_ok=True)
        if kind == "csv":
            path = to_csv(results, out / "matches.csv")
            return PlainTextResponse(path.read_text(encoding="utf-8-sig"),
                                     media_type="text/csv")
        if kind == "json":
            path = to_json(results, out / "matches.json", profile)
            return JSONResponse(json.loads(path.read_text(encoding="utf-8")))
        if kind == "md":
            path = to_markdown(results, out / "matches.md", profile)
            return PlainTextResponse(path.read_text(encoding="utf-8"),
                                     media_type="text/markdown")
        path = to_html(results, out / "matches.html", profile)
        return HTMLResponse(path.read_text(encoding="utf-8"))

    return app


# --------------------------------------------------------------------------- #
PAGE = r"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MagangKu - Dashboard</title>
<style>
:root{--bg:#0a1020;--pan:#111a2e;--card:#16203a;--line:#26324c;--tx:#e8eef9;
--mut:#94a6c4;--ac:#38bdf8;--ok:#22c55e;--wr:#f59e0b;--bad:#ef4444;--vio:#c084fc}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--ac)}
header{background:var(--pan);border-bottom:1px solid var(--line);padding:12px 20px;
display:flex;align-items:center;gap:14px;flex-wrap:wrap;position:sticky;top:0;z-index:30}
h1{margin:0;font-size:17px;color:var(--ac);white-space:nowrap}
h1 span{color:var(--mut);font-weight:400;font-size:12px}
.who{color:var(--mut);font-size:12.5px}
.grow{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
nav{display:flex;gap:4px;padding:0 20px;background:var(--pan);border-bottom:1px solid var(--line);
position:sticky;top:53px;z-index:29;overflow-x:auto}
nav button{background:0;border:0;border-bottom:2px solid transparent;color:var(--mut);
padding:11px 14px;cursor:pointer;font-size:13.5px;white-space:nowrap}
nav button.on{color:var(--ac);border-bottom-color:var(--ac);font-weight:600}
main{padding:18px 20px;max-width:1160px;margin:0 auto}
.hide{display:none!important}
input,select,textarea,button{font-family:inherit}
input,select,textarea{background:var(--card);border:1px solid var(--line);color:var(--tx);
padding:9px 11px;border-radius:8px;font-size:13.5px;outline:none;width:100%}
input:focus,select:focus,textarea:focus{border-color:var(--ac)}
textarea{resize:vertical;font:12.5px/1.5 ui-monospace,Menlo,monospace}
label{display:block;font-size:12px;color:var(--mut);margin:0 0 4px}
.fld{margin-bottom:12px}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.btn{background:var(--ac);color:#052a3d;border:0;font-weight:700;padding:9px 15px;
border-radius:8px;font-size:13px;cursor:pointer;text-decoration:none;display:inline-block;
text-align:center;white-space:nowrap}
.btn:hover{filter:brightness(1.09)}
.btn.gh{background:transparent;border:1px solid var(--line);color:var(--mut)}
.btn.sm{padding:6px 11px;font-size:12px}
.btn:disabled{opacity:.5;cursor:not-allowed}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:14px}
.panel h2{margin:0 0 4px;font-size:15.5px}
.panel .sub{color:var(--mut);font-size:12.5px;margin:0 0 14px}
.tools{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:14px}
.tools>*{flex:0 0 auto;width:auto}
.tools #q{flex:1 1 210px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 15px;
margin-bottom:9px;display:grid;grid-template-columns:66px 1fr auto;gap:13px;align-items:start;cursor:pointer}
.card:hover{border-color:var(--ac)}
.sc{font-size:24px;font-weight:800;line-height:1}
.sc small{display:block;font-size:10px;color:var(--mut);font-weight:400}
.s-strong{color:var(--ok)}.s-good{color:var(--ac)}.s-maybe{color:var(--wr)}.s-weak{color:var(--mut)}
.card h3{margin:0 0 2px;font-size:15px}
.co{margin:0 0 7px;color:var(--mut);font-size:12.5px}
.chips{display:flex;gap:5px;flex-wrap:wrap}
.chip{background:#1d2942;border:1px solid var(--line);color:var(--mut);font-size:11px;padding:2px 8px;border-radius:99px}
.chip.ok{color:var(--ok);border-color:#14532d}.chip.warn{color:var(--wr);border-color:#78350f}
.chip.gov{color:var(--vio);border-color:#581c87}.chip.trk{color:var(--ac);border-color:#075985}
.act{display:flex;flex-direction:column;gap:5px}
.empty{text-align:center;color:var(--mut);padding:44px 18px}
.note{padding:10px 13px;border-radius:8px;font-size:12.5px;margin-bottom:12px;border:1px solid}
.note.w{background:#3b2a08;border-color:#78350f;color:#fcd34d}
.note.g{background:#052e16;border-color:#14532d;color:#86efac}
.note.i{background:#082f49;border-color:#075985;color:#7dd3fc}
.note.e{background:#3f1010;border-color:#7f1d1d;color:#fca5a5}
pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:12px;
white-space:pre-wrap;font:12.5px/1.55 ui-monospace,Menlo,monospace;max-height:330px;overflow:auto}
dialog{background:var(--pan);color:var(--tx);border:1px solid var(--line);border-radius:14px;
max-width:820px;width:94%;padding:0}
dialog::backdrop{background:rgba(0,0,0,.72)}
.dh{padding:15px 19px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;
gap:13px;align-items:flex-start;position:sticky;top:0;background:var(--pan)}
.db{padding:15px 19px;max-height:66vh;overflow:auto}
.x{background:0;border:0;color:var(--mut);font-size:23px;cursor:pointer;line-height:1;width:auto}
.tabs{display:flex;gap:5px;margin-bottom:12px;flex-wrap:wrap}
.tab{background:var(--card);border:1px solid var(--line);color:var(--mut);padding:6px 12px;
border-radius:7px;cursor:pointer;font-size:12.5px;width:auto}
.tab.on{background:var(--ac);color:#052a3d;font-weight:700}
.bar{height:6px;background:#1d2942;border-radius:4px;overflow:hidden;margin:4px 0 8px}
.bar i{display:block;height:100%;background:var(--ac)}
.cmp{font-size:12.5px;margin-bottom:8px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 9px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:600;font-size:12px}
.steps{counter-reset:s;padding-left:0;list-style:none;margin:0}
.steps li{counter-increment:s;position:relative;padding-left:32px;margin-bottom:11px;font-size:13.5px}
.steps li::before{content:counter(s);position:absolute;left:0;top:0;width:22px;height:22px;
background:var(--ac);color:#052a3d;border-radius:50%;display:grid;place-items:center;font-size:12px;font-weight:700}
.sw{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--tx);margin-bottom:9px;cursor:pointer}
.sw input{width:auto}
.rng{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.rng label{margin:0;width:96px;text-transform:capitalize;color:var(--tx);font-size:13px}
.rng input{flex:1;width:auto}
.rng b{width:44px;text-align:right;color:var(--ac);font-size:12.5px}
@media(max-width:700px){.card{grid-template-columns:52px 1fr}.act{grid-column:1/-1;flex-direction:row}}
</style></head><body>

<header>
  <h1>MagangKu <span id="src"></span></h1>
  <div class="who" id="who">memuat...</div>
  <div class="grow">
    <button class="btn gh sm" id="btnRefresh">Perbarui data</button>
    <span class="chip" id="pill"></span>
  </div>
</header>

<nav>
  <button class="on" data-v="cari">Cari Lowongan</button>
  <button data-v="profil">Profil Saya</button>
  <button data-v="hubung">Hubungkan MagangHub</button>
  <button data-v="lamaran">Lamaran</button>
  <button data-v="bantuan">Bantuan</button>
</nav>

<main>
  <div id="msg"></div>

  <!-- ONBOARDING ------------------------------------------------------- -->
  <section id="v-onboard" class="hide">
    <div class="panel">
      <h2>Selamat datang di MagangKu</h2>
      <p class="sub">Tiga langkah singkat supaya rekomendasinya benar-benar sesuai Anda.</p>
      <ol class="steps">
        <li><b>Isi profil Anda</b> - ketik manual, tempel CV, atau impor dari MagangHub.
          <div style="margin-top:7px"><button class="btn sm" onclick="go('profil')">Buka Profil</button>
          <button class="btn gh sm" onclick="go('hubung')">Impor dari MagangHub</button></div></li>
        <li><b>Ambil data lowongan</b> - dari server Kemnaker, atau pakai data contoh bila jaringan diblokir.
          <div style="margin-top:7px"><button class="btn sm" onclick="refresh('live')">Ambil data live</button>
          <button class="btn gh sm" onclick="refresh('fixtures')">Pakai data contoh</button></div></li>
        <li><b>Lihat hasilnya</b> - lowongan diurutkan berdasar kecocokan dengan profil Anda.
          <div style="margin-top:7px"><button class="btn sm" onclick="go('cari')">Lihat Lowongan</button></div></li>
      </ol>
    </div>
  </section>

  <!-- CARI ------------------------------------------------------------- -->
  <section id="v-cari">
    <div class="tools">
      <input id="q" placeholder="Cari posisi, perusahaan, kota...">
      <select id="min"><option value="0">Semua skor</option><option value="45">&ge;45</option>
        <option value="60">&ge;60</option><option value="75">&ge;75</option></select>
      <select id="vd"><option value="">Semua kategori</option><option value="strong">Sangat cocok</option>
        <option value="good">Cocok</option><option value="maybe">Pertimbangkan</option>
        <option value="weak">Kurang cocok</option></select>
      <select id="pv"><option value="">Semua provinsi</option></select>
      <select id="gv"><option value="">Semua instansi</option><option value="1">Pemerintah</option>
        <option value="0">Swasta</option></select>
      <select id="tk"><option value="">Semua status</option><option value="1">Sudah ditandai</option>
        <option value="0">Belum ditandai</option></select>
      <a class="btn gh sm" href="/api/export/csv" target="_blank">CSV</a>
      <a class="btn gh sm" href="/api/export/html" target="_blank">HTML</a>
    </div>
    <div id="list" class="empty">Memuat...</div>
  </section>

  <!-- PROFIL ----------------------------------------------------------- -->
  <section id="v-profil" class="hide">
    <div class="panel">
      <h2>Data diri</h2>
      <p class="sub">Dipakai untuk menghitung kecocokan dan menulis surat lamaran.</p>
      <div class="row">
        <div class="fld"><label>Nama lengkap</label><input id="f_name"></div>
        <div class="fld"><label>Email</label><input id="f_email"></div>
        <div class="fld"><label>No. HP</label><input id="f_phone"></div>
        <div class="fld"><label>Kota domisili</label><input id="f_city"></div>
        <div class="fld"><label>Kampus / sekolah</label><input id="f_university"></div>
        <div class="fld"><label>Jenjang</label>
          <select id="f_level">
            <option value="">- pilih -</option><option>SMA/SMK sederajat</option>
            <option>Diploma III</option><option>Diploma IV</option>
            <option>Sarjana</option><option>Magister</option><option>Doktor</option>
          </select></div>
        <div class="fld"><label>IPK</label><input id="f_gpa"></div>
      </div>
    </div>

    <div class="panel">
      <h2>Jurusan &amp; keahlian</h2>
      <p class="sub">Pisahkan dengan koma. Sinonim sudah dikenali otomatis
        (mis. <i>Informatika</i> cocok dengan <i>Ilmu Komputer</i>).</p>
      <div class="fld"><label>Program studi utama</label><input id="f_majors"></div>
      <div class="fld"><label>Jurusan alternatif (bobot lebih rendah)</label><input id="f_adjacent_majors"></div>
      <div class="fld"><label>Keahlian</label><input id="f_skills"></div>
    </div>

    <div class="panel">
      <h2>Lokasi &amp; penyaringan</h2>
      <div class="row">
        <div class="fld"><label>Kota prioritas</label><input id="f_cities"></div>
        <div class="fld"><label>Provinsi yang diterima</label><input id="f_provinces"></div>
      </div>
      <label class="sw"><input type="checkbox" id="f_allow_outside"> Tetap tampilkan lowongan di luar preferensi (skor lebih rendah)</label>
      <label class="sw"><input type="checkbox" id="f_only_open"> Sembunyikan yang pendaftarannya sudah tutup</label>
      <label class="sw"><input type="checkbox" id="f_government_only"> Hanya instansi pemerintah</label>
      <div class="row">
        <div class="fld"><label>Kuota minimum</label><input id="f_min_quota" type="number" min="0"></div>
        <div class="fld"><label>Maks pelamar per slot (0 = bebas)</label><input id="f_max_competition" type="number" min="0"></div>
      </div>
      <div class="fld"><label>Kata kunci yang dibuang</label><input id="f_exclude_keywords"></div>
    </div>

    <div class="panel">
      <h2>Bobot penilaian</h2>
      <p class="sub">Geser sesuai yang paling Anda pedulikan. Total dinormalkan otomatis.</p>
      <div id="weights"></div>
    </div>

    <div class="panel">
      <h2>Isi otomatis dari CV</h2>
      <p class="sub">Tempel teks CV Anda - nama, kampus, jenjang, IPK, jurusan, dan keahlian
        akan dideteksi. Nilai yang sudah Anda isi tidak akan ditimpa.</p>
      <div class="fld"><textarea id="cvText" rows="7" placeholder="Tempel isi CV Anda di sini..."></textarea></div>
      <button class="btn" id="btnCv">Deteksi &amp; isikan</button>
    </div>

    <div style="display:flex;gap:9px;flex-wrap:wrap;margin-bottom:20px">
      <button class="btn" id="btnSave">Simpan profil</button>
      <button class="btn gh" id="btnYaml">Edit YAML mentah</button>
    </div>

    <div class="panel hide" id="yamlBox">
      <h2>profile.yml</h2>
      <p class="sub">Untuk pengaturan lanjutan yang tidak ada di formulir.</p>
      <div class="fld"><textarea id="yamlText" rows="18"></textarea></div>
      <button class="btn" id="btnYamlSave">Simpan YAML</button>
    </div>
  </section>

  <!-- HUBUNGKAN -------------------------------------------------------- -->
  <section id="v-hubung" class="hide">
    <div class="note i">
      <b>MagangKu tidak pernah meminta password Anda.</b><br>
      Akun SIAPkerja terhubung dengan NIK/Dukcapil - itu identitas kependudukan Anda,
      bukan sekadar login biasa. Semua cara di bawah berjalan lokal di komputer Anda.
    </div>

    <div class="panel">
      <h2>Cara 1 - Tempel JSON profil <span class="chip ok">paling aman</span></h2>
      <p class="sub">Tidak ada token yang berpindah tangan sama sekali.</p>
      <ol class="steps">
        <li>Login ke <a href="https://maganghub.kemnaker.go.id" target="_blank" rel="noopener">maganghub.kemnaker.go.id</a>, buka halaman profil Anda.</li>
        <li>Tekan <b>F12</b> &rarr; tab <b>Network</b> &rarr; muat ulang halaman (F5).</li>
        <li>Cari permintaan XHR/fetch yang isinya data profil Anda (ada nama &amp; pendidikan).</li>
        <li>Klik kanan &rarr; <b>Copy</b> &rarr; <b>Copy response</b>, lalu tempel di bawah.</li>
      </ol>
      <div class="fld" style="margin-top:12px">
        <textarea id="syncJson" rows="8" placeholder='{"data":{"nama_lengkap":"...","pendidikan":[...]}}'></textarea>
      </div>
      <label class="sw"><input type="checkbox" id="syncOverwrite"> Timpa juga nilai yang sudah saya isi sendiri</label>
      <div style="display:flex;gap:9px;flex-wrap:wrap">
        <button class="btn gh" id="btnSyncPreview">Pratinjau perubahan</button>
        <button class="btn" id="btnSyncApply">Impor ke profil saya</button>
      </div>
      <div id="syncOut"></div>
    </div>

    <div class="panel">
      <h2>Cara 2 - Sesi cookie</h2>
      <p class="sub">Isi <code>MAGANGHUB_COOKIE</code> di berkas <code>.env</code>
        (sudah masuk .gitignore), lalu uji di sini.</p>
      <div id="sessBox" class="note w">Memeriksa...</div>
      <div style="display:flex;gap:9px;flex-wrap:wrap">
        <button class="btn gh" id="btnSessTest">Uji koneksi sesi</button>
        <button class="btn gh" id="btnSyncAuto">Impor otomatis</button>
      </div>
      <div id="sessOut"></div>
    </div>

    <div class="panel">
      <h2>Cek endpoint API Kemnaker</h2>
      <p class="sub">Kemnaker memindahkan MagangHub ke gateway baru
        (<code>api.kemnaker.go.id</code>). Sebagian alamat di bawah masih
        <b>tebakan</b> karena tidak bisa diuji dari lingkungan pembuatan.
        Klik tombol ini dari koneksi internet Anda untuk melihat mana yang
        benar-benar hidup.</p>
      <div style="display:flex;gap:9px;flex-wrap:wrap">
        <button class="btn gh" id="btnProbe">Uji semua endpoint</button>
      </div>
      <div id="probeOut"></div>
    </div>

    <div class="panel">
      <h2>Yang tidak akan pernah dilakukan MagangKu</h2>
      <ul style="color:var(--mut);font-size:13px;margin:0;padding-left:19px">
        <li>Meminta atau menyimpan password Anda</li>
        <li>Mengirim data ke server mana pun selain kemnaker.go.id</li>
        <li>Mengirim lamaran tanpa Anda sendiri yang menekan tombol kirim</li>
      </ul>
    </div>
  </section>

  <!-- LAMARAN ---------------------------------------------------------- -->
  <section id="v-lamaran" class="hide">
    <div class="panel">
      <h2>Lamaran saya</h2>
      <p class="sub">Status yang Anda tandai dari kartu lowongan.</p>
      <div id="apps">Memuat...</div>
    </div>
  </section>

  <!-- BANTUAN ---------------------------------------------------------- -->
  <section id="v-bantuan" class="hide">
    <div class="panel"><h2>Panduan keamanan &amp; koneksi</h2><pre id="helpText">memuat...</pre></div>
  </section>
</main>

<dialog id="dlg">
  <div class="dh"><div><h3 id="dt" style="margin:0"></h3><div class="co" id="dc"></div></div>
  <button class="x" onclick="document.getElementById('dlg').close()">&times;</button></div>
  <div class="db">
    <div class="tabs">
      <button class="tab on" data-t="why">Analisis</button>
      <button class="tab" data-t="desc">Deskripsi</button>
      <button class="tab" data-t="letter">Surat Lamaran</button>
      <button class="tab" data-t="check">Checklist</button>
    </div>
    <div id="dbody"></div>
  </div>
</dialog>

<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const dlg=$('#dlg'); let cur=null, tab='why', BOOT=null;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const WEIGHTS=['major','skills','location','opportunity','level','urgency'];
const WLABEL={major:'jurusan',skills:'keahlian',location:'lokasi',opportunity:'peluang',level:'jenjang',urgency:'tenggat'};

function flash(html,kind='i',ms=6000){
  const el=document.createElement('div'); el.className='note '+kind; el.innerHTML=html;
  $('#msg').prepend(el); if(ms) setTimeout(()=>el.remove(),ms);
}
function go(v){
  $$('nav button').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
  ['cari','profil','hubung','lamaran','bantuan','onboard']
    .forEach(x=>$('#v-'+x)?.classList.toggle('hide',x!==v));
  if(v==='lamaran') loadApps();
  if(v==='hubung') loadSession();
  if(v==='bantuan') loadHelp();
}
$$('nav button').forEach(b=>b.onclick=()=>go(b.dataset.v));

async function api(url,opt){
  const r=await fetch(url,opt);
  let d=null; try{ d=await r.json(); }catch(e){}
  if(!r.ok) throw new Error(d?.detail||d?.error||('HTTP '+r.status));
  return d;
}

// ---------------------------------------------------------------- boot
async function boot(){
  BOOT=await api('/api/bootstrap');
  if(!BOOT.ready){ flash('Gagal memuat profil: '+esc(BOOT.error),'e',0); return; }
  const p=BOOT.profile;
  $('#who').textContent=`${p.name} - ${(p.majors||[]).join(', ')||'jurusan belum diisi'} - ${p.level||'-'}`;
  $('#src').textContent = BOOT.source==='fixtures' ? '(data contoh)' : '';
  $('#pill').textContent=`${BOOT.stats.total_vacancies} lowongan - ${BOOT.stats.open_vacancies} buka`;
  fillForm(p);
  if(BOOT.using_example)
    flash('Anda masih memakai <b>profil contoh</b>. Isi Profil Saya agar hasilnya relevan. '+
          '<button class="btn sm" onclick="go(\'profil\')">Isi sekarang</button>','w',0);
  else if(BOOT.warnings?.length)
    flash('<b>Profil belum optimal:</b><br>'+BOOT.warnings.map(esc).join('<br>'),'w',9000);
  if(BOOT.needs_onboarding){ go('onboard'); } else { load(); }
}

function fillForm(p){
  const g=k=>$('#f_'+k); if(!g('name')) return;
  api('/api/profile/raw').then(r=>{
    $('#yamlText').value=r.yaml;
    const y=r.yaml;
    const grab=(re)=>{const m=y.match(re);return m?m[1].trim().replace(/^['"]|['"]$/g,''):'';};
    g('name').value=grab(/^\s*name:\s*(.+)$/m); g('email').value=grab(/^\s*email:\s*(.+)$/m);
    g('phone').value=grab(/^\s*phone:\s*(.+)$/m); g('city').value=grab(/^\s*city:\s*(.+)$/m);
    g('university').value=grab(/^\s*university:\s*(.+)$/m);
    g('level').value=grab(/^\s*level:\s*(.+)$/m); g('gpa').value=grab(/^\s*gpa:\s*(.+)$/m);
  });
  g('majors').value=(p.majors||[]).join(', ');
  g('cities').value=(p.cities||[]).join(', ');
  g('provinces').value=(p.provinces||[]).join(', ');
  const w=p.weights||{}; $('#weights').innerHTML=WEIGHTS.map(k=>`
    <div class="rng"><label>${WLABEL[k]}</label>
    <input type="range" min="0" max="50" value="${Math.round((w[k]||0)*100)}" id="w_${k}"
      oninput="this.nextElementSibling.textContent=this.value+'%'">
    <b>${Math.round((w[k]||0)*100)}%</b></div>`).join('');
}

// ---------------------------------------------------------------- matches
function debounce(f,ms){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>f(...a),ms)}}
async function load(){
  const u=new URLSearchParams({q:$('#q').value,min_score:$('#min').value,verdict:$('#vd').value,
    province:$('#pv').value,gov:$('#gv').value,tracked:$('#tk').value});
  let d; try{ d=await api('/api/matches?'+u); }catch(e){ flash('Gagal memuat: '+esc(e.message),'e'); return; }
  if($('#pv').options.length<2) d.provinces.forEach(p=>$('#pv').add(new Option(p,p)));
  const L=$('#list');
  if(!d.results.length){
    L.className='empty';
    L.innerHTML='Tidak ada lowongan yang cocok dengan filter ini.<br><br>'+
      '<button class="btn gh sm" onclick="refresh(\'fixtures\')">Muat data contoh</button> '+
      '<button class="btn gh sm" onclick="go(\'profil\')">Longgarkan filter di Profil</button>';
    return;
  }
  L.className='';
  L.innerHTML=d.results.map(r=>{
    const days=r.days_left!=null?`<span class="chip ${r.days_left<=7?'warn':''}">${r.days_left} hari lagi</span>`:'';
    const gov=r.is_government?'<span class="chip gov">Pemerintah</span>':'';
    const trk=r.tracked_status?`<span class="chip trk">${esc(r.tracked_status)}</span>`:'';
    return `<div class="card" onclick="openV('${r.id}')">
      <div class="sc s-${r.verdict}">${r.score}<small>/100</small></div>
      <div><h3>${esc(r.position)}</h3><p class="co">${esc(r.company)} &middot; ${esc(r.location)}</p>
      <div class="chips"><span class="chip">Kuota ${r.quota}</span>
      <span class="chip">${r.registered} pelamar</span>
      <span class="chip ok">est. ${Math.round(r.acceptance_estimate*100)}%</span>${days}${gov}${trk}</div></div>
      <div class="act">
        <a class="btn sm" href="${esc(r.apply_url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Apply</a>
        <button class="btn gh sm" onclick="event.stopPropagation();track('${r.id}','shortlisted')">Simpan</button>
      </div></div>`;
  }).join('');
}
['q'].forEach(i=>$('#'+i).addEventListener('input',debounce(load,280)));
['min','vd','pv','gv','tk'].forEach(i=>$('#'+i).addEventListener('change',load));

async function openV(id){
  try{ cur=await api('/api/vacancy/'+id); }catch(e){ flash(esc(e.message),'e'); return; }
  $('#dt').textContent=cur.position; $('#dc').textContent=`${cur.company} - ${cur.location}`;
  tab='why'; $$('.tab').forEach(t=>t.classList.toggle('on',t.dataset.t==='why'));
  renderTab(); dlg.showModal();
}
function renderTab(){
  const c=cur,b=$('#dbody');
  if(tab==='why'){
    b.innerHTML=`<p><b>Skor ${c.score}/100</b> - ${esc(c.verdict)}</p>`+
      c.components.map(x=>`<div class="cmp"><b>${WLABEL[x.key]||x.key}</b> - ${esc(x.reason)}
        <div class="bar"><i style="width:${x.score*100}%"></i></div>
        <span style="color:var(--mut)">kontribusi ${x.contribution} poin (bobot ${Math.round(x.weight*100)}%)</span></div>`).join('')+
      (c.bonuses?.length?`<p style="color:var(--ok)">Bonus: ${c.bonuses.map(x=>esc(x.label)+' +'+x.points).join(', ')}</p>`:'')+
      `<p style="color:var(--mut);font-size:12.5px">Persaingan ${c.competition_ratio}:1 &middot; batas ${esc(c.deadline||'-')}</p>
       <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
         <a class="btn" href="${esc(c.apply_url)}" target="_blank" rel="noopener">Buka halaman apply</a>
         <button class="btn gh" onclick="track('${c.id}','applied')">Tandai sudah dilamar</button>
       </div>`;
  } else if(tab==='desc'){
    b.innerHTML=`<p><b>Jurusan:</b> ${esc((c.majors||[]).join(', ')||'bebas')}</p>
      <p><b>Jenjang:</b> ${esc((c.levels||[]).join(', ')||'bebas')}</p>
      <p><b>Alamat:</b> ${esc(c.address||'-')}</p>
      <pre>${esc(c.description||'(tidak ada)')}</pre>
      ${c.requirements?`<p><b>Syarat khusus</b></p><pre>${esc(c.requirements)}</pre>`:''}`;
  } else if(tab==='letter'){
    b.innerHTML=`<p style="color:var(--mut);font-size:12.5px">Sunting seperlunya sebelum dikirim.</p>
      <pre id="lt">${esc(c.letter)}</pre><button class="btn" onclick="copyEl('lt')">Salin surat</button>`;
  } else {
    b.innerHTML=`<pre>${esc(c.checklist)}</pre>`;
  }
}
$$('.tab').forEach(t=>t.onclick=()=>{tab=t.dataset.t;$$('.tab').forEach(x=>x.classList.remove('on'));t.classList.add('on');renderTab();});
function copyEl(id){navigator.clipboard.writeText($('#'+id).textContent);flash('Surat disalin.','g',2500);}
async function track(id,st){ await api(`/api/track/${id}?status=${st}`,{method:'POST'}); flash('Ditandai: '+st,'g',2200); load(); }

// ---------------------------------------------------------------- refresh
async function refresh(source){
  const btn=$('#btnRefresh'); btn.disabled=true; btn.textContent='Mengambil...';
  try{
    const d=await api('/api/refresh',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({source})});
    if(!d.ok){
      flash(`<b>Gagal ambil data live.</b> ${esc(d.error)}<br>${esc(d.hint||'')}
        <br><button class="btn sm" onclick="refresh('fixtures')">Pakai data contoh</button>`,'w',0);
    } else {
      flash(`${esc(d.note)} <b>${d.total}</b> lowongan (${d.new} baru, ${d.changed} berubah).`,'g');
      const s=await api('/api/stats');
      $('#pill').textContent=`${s.total_vacancies} lowongan - ${s.open_vacancies} buka`;
      go('cari'); load();
    }
  }catch(e){ flash('Gagal: '+esc(e.message),'e'); }
  btn.disabled=false; btn.textContent='Perbarui data';
}
$('#btnRefresh').onclick=()=>refresh(BOOT?.source==='fixtures'?'fixtures':'live');

// ---------------------------------------------------------------- profile
$('#btnSave').onclick=async()=>{
  const g=k=>$('#f_'+k).value;
  const form={name:g('name'),email:g('email'),phone:g('phone'),city:g('city'),
    university:g('university'),level:g('level'),gpa:g('gpa'),
    majors:g('majors'),adjacent_majors:g('adjacent_majors'),skills:g('skills'),
    cities:g('cities'),provinces:g('provinces'),
    allow_outside:$('#f_allow_outside').checked,only_open:$('#f_only_open').checked,
    government_only:$('#f_government_only').checked,
    min_quota:g('min_quota')||0,max_competition:g('max_competition')||0,
    exclude_keywords:g('exclude_keywords')};
  const weights={}; WEIGHTS.forEach(k=>weights[k]=(+$('#w_'+k).value)/100);
  try{
    await api('/api/profile/save',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({form,weights})});
    flash('Profil tersimpan. Skor dihitung ulang.','g'); await boot(); go('cari');
  }catch(e){ flash('Gagal menyimpan: '+esc(e.message),'e'); }
};
$('#btnYaml').onclick=()=>$('#yamlBox').classList.toggle('hide');
$('#btnYamlSave').onclick=async()=>{
  try{
    await api('/api/profile/raw',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({yaml:$('#yamlText').value})});
    flash('YAML tersimpan.','g'); boot();
  }catch(e){ flash(esc(e.message),'e'); }
};
$('#btnCv').onclick=async()=>{
  const text=$('#cvText').value;
  if(text.trim().length<30){ flash('Teks CV terlalu pendek.','w'); return; }
  try{
    const d=await api('/api/profile/from-cv',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text,apply:true})});
    const i=d.parsed.identity;
    flash(`Terdeteksi: <b>${esc(i.name||'-')}</b>, ${esc(i.level||'-')},
      ${esc(i.university||'-')}, ${d.parsed.skills.length} keahlian. Periksa lalu simpan.`,'g',9000);
    await boot(); go('profil');
  }catch(e){ flash(esc(e.message),'e'); }
};

// ---------------------------------------------------------------- session/sync
async function loadSession(){
  try{
    const d=await api('/api/session');
    $('#sessBox').className='note '+(d.connected?'g':'w');
    $('#sessBox').innerHTML = d.connected
      ? `Sesi aktif dari <b>${esc(d.summary.source)}</b> - ${d.summary.cookie_count} cookie,
         token ${d.summary.has_access_token?'ditemukan ('+esc(d.summary.token_preview)+')':'tidak ada'}.`
      : 'Belum ada sesi. Itu wajar - pencarian lowongan tetap jalan tanpa login.';
  }catch(e){ $('#sessBox').textContent='Gagal memeriksa sesi.'; }
}
$('#btnSessTest').onclick=async()=>{
  $('#sessOut').innerHTML='<div class="note i">Menguji...</div>';
  try{
    const d=await api('/api/session/test',{method:'POST'});
    $('#sessOut').innerHTML=`<div class="note ${d.ok?'g':'w'}">${d.ok
      ? 'Berhasil: <b>'+esc(d.endpoint)+'</b>' : 'Tidak ada endpoint yang merespons.'}</div>
      <pre>${esc((d.log||[]).join('\n'))}</pre>`;
  }catch(e){ $('#sessOut').innerHTML=`<div class="note e">${esc(e.message)}</div>`; }
};
$('#btnProbe').onclick=async()=>{
  $('#probeOut').innerHTML='<div class="note i">Menguji semua endpoint, mohon tunggu...</div>';
  try{
    const d=await api('/api/probe',{method:'POST',
      headers:{'Content-Type':'application/json'},body:'{}'});
    const groups={};
    (d.results||[]).forEach(r=>{ (groups[r.kind]=groups[r.kind]||[]).push(r); });
    let html=`<div class="note ${d.alive?'g':'w'}">${d.alive} dari ${d.total}
      endpoint merespons.${d.has_session?'':' (tanpa sesi login - endpoint privat pasti gagal)'}</div>`;
    for(const k of Object.keys(groups)){
      html+=`<div style="margin-top:10px"><b style="font-size:12px;
        text-transform:uppercase;color:var(--mut)">${esc(k)}</b>`;
      groups[k].forEach(r=>{
        const badge=r.ok?'g':'e';
        const detail=r.ok
          ? `${r.items} item${r.total?', total '+r.total:''}${r.note?' | '+esc(r.note):''}`
          : `${r.status||'---'} ${esc(r.note||'')}`;
        html+=`<div class="note ${badge}" style="margin:5px 0">
          <div style="font-family:ui-monospace,monospace;font-size:11px;
            word-break:break-all">${esc(r.url)}</div>
          <div style="font-size:11px;color:var(--mut);margin-top:3px">${detail}
            &nbsp;·&nbsp;<i>${esc(r.confidence_label||r.confidence)}</i></div></div>`;
      });
      html+='</div>';
    }
    if(d.alive){
      html+=`<p class="sub" style="margin-top:10px">Untuk memakai endpoint
        lowongan yang hidup, set <code>MAGANGKU_BASE_URL</code> di
        <code>.env</code> lalu jalankan ulang.</p>`;
    }
    $('#probeOut').innerHTML=html;
  }catch(e){ $('#probeOut').innerHTML=`<div class="note e">${esc(e.message)}</div>`; }
};
async function doSync(dry){
  const raw=$('#syncJson').value.trim();
  const body={overwrite:$('#syncOverwrite').checked,dry_run:dry};
  if(raw) body.json=raw;
  $('#syncOut').innerHTML='<div class="note i">Memproses...</div>';
  try{
    const d=await api('/api/sync',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)});
    const f=d.found;
    $('#syncOut').innerHTML=`<div class="note g">
      Terbaca: ${f.identity_fields.length} field identitas, ${f.majors} jurusan,
      ${f.skills} keahlian${f.province?', provinsi '+esc(f.province):''}.</div>
      ${d.changes.length?'<pre>'+esc(d.changes.join('\n'))+'</pre>'
        :'<div class="note i">Tidak ada perubahan - profil sudah selaras.</div>'}
      ${d.applied?'<div class="note g">Profil diperbarui.</div>':''}`;
    if(d.applied){ await boot(); }
  }catch(e){ $('#syncOut').innerHTML=`<div class="note e">${esc(e.message)}</div>`; }
}
$('#btnSyncPreview').onclick=()=>doSync(true);
$('#btnSyncApply').onclick=()=>doSync(false);
$('#btnSyncAuto').onclick=()=>{ $('#syncJson').value=''; doSync(false); };

// ---------------------------------------------------------------- apps/help
async function loadApps(){
  const d=await api('/api/applications');
  if(!d.applications.length){
    $('#apps').innerHTML='<div class="empty">Belum ada lamaran ditandai.<br>'+
      'Buka sebuah lowongan lalu tekan <b>Simpan</b> atau <b>Tandai sudah dilamar</b>.</div>';
    return;
  }
  $('#apps').innerHTML=`<table><tr><th>Status</th><th>Skor</th><th>Posisi</th>
    <th>Perusahaan</th><th>Batas</th><th>Ubah</th></tr>`+
    d.applications.map(a=>`<tr>
      <td><span class="chip trk">${esc(a.status)}</span></td>
      <td>${a.score?Math.round(a.score):'-'}</td>
      <td>${esc(a.position||'-')}</td><td>${esc(a.company||'-')}</td>
      <td>${esc(a.deadline||'-')}</td>
      <td><select onchange="track('${a.vacancy_id}',this.value)">
        ${d.statuses.map(s=>`<option ${s===a.status?'selected':''}>${s}</option>`).join('')}
      </select></td></tr>`).join('')+'</table>';
}
async function loadHelp(){ try{ $('#helpText').textContent=(await api('/api/session')).help; }catch(e){} }

boot();
</script></body></html>"""
