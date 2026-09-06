"""FastAPI dashboard: browse, filter, score and shortlist vacancies visually.

Single-file app (HTML+CSS+JS inlined) so there is no build step and no CDN
dependency - it works fully offline.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from .letter import build_checklist, build_letter
from .matcher import Matcher
from .models import Vacancy
from .profile import Profile, default_profile_path
from .scraper import load_fixtures
from .storage import VALID_STATUSES, Store

ROOT = Path(__file__).resolve().parent.parent


def _load_state() -> tuple[Profile, Store, list[Vacancy]]:
    profile = Profile.load(default_profile_path(os.getenv("MAGANGKU_PROFILE")))
    store = Store(os.getenv("MAGANGKU_DB") or ROOT / "magangku.db")
    source = os.getenv("MAGANGKU_SOURCE", "db")
    vacancies = load_fixtures() if source == "fixtures" else (store.all_vacancies() or load_fixtures())
    return profile, store, vacancies


def create_app() -> FastAPI:
    app = FastAPI(title="MagangKu Dashboard", docs_url="/api/docs")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE

    @app.get("/api/profile")
    def api_profile() -> dict[str, Any]:
        profile, _, _ = _load_state()
        return {"summary": profile.summary(), "warnings": profile.validate()}

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
            row = r.to_dict()
            row["tracked_status"] = store.application_status(v.id)
            items.append(row)
            if len(items) >= limit:
                break

        provinces = sorted({v.province.title() for v in vacancies if v.province})
        return {"count": len(items), "results": items, "provinces": provinces}

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
            raise HTTPException(400, f"Status tidak valid. Pilih: {', '.join(VALID_STATUSES)}")
        _, store, _ = _load_state()
        store.track(vacancy_id, status=status)
        return JSONResponse({"ok": True, "vacancy_id": vacancy_id, "status": status})

    @app.get("/api/applications")
    def api_applications() -> dict[str, Any]:
        _, store, _ = _load_state()
        return {"applications": store.applications()}

    return app


PAGE = """<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MagangKu - Dashboard</title>
<style>
:root{--bg:#0a1020;--pan:#111a2e;--card:#16203a;--line:#26324c;--tx:#e8eef9;--mut:#94a6c4;--ac:#38bdf8;--ok:#22c55e;--wr:#f59e0b;--bad:#ef4444}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{background:var(--pan);border-bottom:1px solid var(--line);padding:14px 22px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;position:sticky;top:0;z-index:20}
h1{margin:0;font-size:18px;color:var(--ac);white-space:nowrap}
.who{color:var(--mut);font-size:12.5px}
.stat{margin-left:auto;display:flex;gap:16px;font-size:12.5px;color:var(--mut);flex-wrap:wrap}
.stat b{color:var(--tx);font-size:15px}
.tools{display:flex;gap:10px;padding:14px 22px;flex-wrap:wrap;background:var(--pan);border-bottom:1px solid var(--line);position:sticky;top:57px;z-index:19}
input,select{background:var(--card);border:1px solid var(--line);color:var(--tx);padding:9px 12px;border-radius:8px;font-size:13.5px;outline:none}
input:focus,select:focus{border-color:var(--ac)}
#q{flex:1;min-width:200px}
main{padding:18px 22px;max-width:1180px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:10px;display:grid;grid-template-columns:70px 1fr auto;gap:14px;align-items:start;cursor:pointer;transition:border-color .15s}
.card:hover{border-color:var(--ac)}
.sc{font-size:25px;font-weight:800;line-height:1}
.sc small{display:block;font-size:10px;color:var(--mut);font-weight:400;margin-top:2px}
.s-strong{color:var(--ok)}.s-good{color:var(--ac)}.s-maybe{color:var(--wr)}.s-weak{color:var(--mut)}
h3{margin:0 0 3px;font-size:15.5px}
.co{margin:0 0 8px;color:var(--mut);font-size:13px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{background:#1d2942;border:1px solid var(--line);color:var(--mut);font-size:11px;padding:3px 8px;border-radius:99px}
.chip.ok{color:var(--ok);border-color:#14532d}.chip.warn{color:var(--wr);border-color:#78350f}
.chip.gov{color:#c084fc;border-color:#581c87}.chip.trk{color:#38bdf8;border-color:#075985}
.act{display:flex;flex-direction:column;gap:6px;align-items:stretch}
.btn{background:var(--ac);color:#052a3d;border:0;font-weight:700;padding:8px 13px;border-radius:8px;font-size:12.5px;cursor:pointer;text-decoration:none;text-align:center;white-space:nowrap}
.btn.gh{background:transparent;border:1px solid var(--line);color:var(--mut)}
.btn:hover{filter:brightness(1.08)}
.empty{text-align:center;color:var(--mut);padding:50px 20px}
dialog{background:var(--pan);color:var(--tx);border:1px solid var(--line);border-radius:14px;max-width:800px;width:94%;padding:0}
dialog::backdrop{background:rgba(0,0,0,.7)}
.dh{padding:16px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:14px;align-items:flex-start;position:sticky;top:0;background:var(--pan)}
.db{padding:16px 20px;max-height:66vh;overflow:auto}
.x{background:0;border:0;color:var(--mut);font-size:24px;cursor:pointer;line-height:1}
pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:13px;white-space:pre-wrap;font:12.5px/1.55 ui-monospace,Menlo,monospace;max-height:340px;overflow:auto}
.tabs{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap}
.tab{background:var(--card);border:1px solid var(--line);color:var(--mut);padding:6px 12px;border-radius:7px;cursor:pointer;font-size:12.5px}
.tab.on{background:var(--ac);color:#052a3d;font-weight:700;border-color:var(--ac)}
.bar{height:7px;background:#1d2942;border-radius:4px;overflow:hidden;margin:4px 0 9px}
.bar i{display:block;height:100%;background:var(--ac)}
.cmp{font-size:12.5px;margin-bottom:9px}
.cmp b{text-transform:capitalize}
.warnbox{background:#3b2a08;border:1px solid #78350f;color:#fcd34d;padding:9px 13px;border-radius:8px;font-size:12.5px;margin-bottom:12px}
@media(max-width:700px){.card{grid-template-columns:56px 1fr}.act{grid-column:1/-1;flex-direction:row}}
</style></head><body>
<header>
  <h1>MagangKu</h1><div class="who" id="who">memuat...</div>
  <div class="stat" id="stat"></div>
</header>
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
</div>
<main><div id="warn"></div><div id="list" class="empty">Memuat data...</div></main>

<dialog id="dlg"><div class="dh"><div><h3 id="dt"></h3><div class="co" id="dc"></div></div>
<button class="x" onclick="dlg.close()">&times;</button></div>
<div class="db"><div class="tabs">
<button class="tab on" data-t="why">Analisis</button>
<button class="tab" data-t="desc">Deskripsi</button>
<button class="tab" data-t="letter">Surat Lamaran</button>
<button class="tab" data-t="check">Checklist</button></div>
<div id="dbody"></div></div></dialog>

<script>
const $=s=>document.querySelector(s), dlg=$('#dlg');
let cur=null, tab='why';

async function boot(){
  const p=await (await fetch('/api/profile')).json();
  const s=p.summary;
  $('#who').textContent=`${s.name} - ${(s.majors||[]).join(', ')||'-'} - ${s.level}`;
  if(p.warnings?.length) $('#warn').innerHTML=`<div class="warnbox"><b>Profil belum optimal:</b><br>${p.warnings.join('<br>')}</div>`;
  const st=await (await fetch('/api/stats')).json();
  $('#stat').innerHTML=`<span><b>${st.loaded}</b> lowongan</span><span><b>${st.open_vacancies}</b> masih buka</span>`;
  load();
}
function debounce(f,ms){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>f(...a),ms)}}

async function load(){
  const u=new URLSearchParams({q:$('#q').value,min_score:$('#min').value,
    verdict:$('#vd').value,province:$('#pv').value,gov:$('#gv').value});
  const d=await (await fetch('/api/'+'matches?'+u)).json();
  if($('#pv').options.length<2)
    d.provinces.forEach(p=>$('#pv').add(new Option(p,p)));
  const L=$('#list');
  if(!d.results.length){L.className='empty';L.textContent='Tidak ada lowongan yang cocok dengan filter ini.';return;}
  L.className='';
  L.innerHTML=d.results.map(r=>{
    const days=r.days_left!=null?`<span class="chip ${r.days_left<=7?'warn':''}">${r.days_left} hari lagi</span>`:'';
    const gov=r.is_government?'<span class="chip gov">Pemerintah</span>':'';
    const trk=r.tracked_status?`<span class="chip trk">${r.tracked_status}</span>`:'';
    return `<div class="card" onclick="open_('${r.id}')">
      <div class="sc s-${r.verdict}">${r.score}<small>/100</small></div>
      <div><h3>${esc(r.position)}</h3><p class="co">${esc(r.company)} &middot; ${esc(r.location)}</p>
      <div class="chips"><span class="chip">Kuota ${r.quota}</span>
      <span class="chip">${r.registered} pelamar</span>
      <span class="chip ok">est. ${Math.round(r.acceptance_estimate*100)}%</span>${days}${gov}${trk}</div></div>
      <div class="act"><a class="btn" href="${r.apply_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Apply</a>
      <button class="btn gh" onclick="event.stopPropagation();track('${r.id}','shortlisted')">Simpan</button></div></div>`;
  }).join('');
}
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function open_(id){
  cur=await (await fetch('/api/vacancy/'+id)).json();
  $('#dt').textContent=cur.position;
  $('#dc').textContent=`${cur.company} - ${cur.location}`;
  tab='why';document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.t==='why'));
  render();dlg.showModal();
}
function render(){
  const c=cur,b=$('#dbody');
  if(tab==='why'){
    b.innerHTML=`<p><b>Skor ${c.score}/100</b> &mdash; ${c.verdict}</p>`+
      c.components.map(x=>`<div class="cmp"><b>${x.key}</b> &mdash; ${esc(x.reason)}
      <div class="bar"><i style="width:${x.score*100}%"></i></div>
      <span style="color:var(--mut)">kontribusi ${x.contribution} poin (bobot ${Math.round(x.weight*100)}%)</span></div>`).join('')+
      (c.bonuses?.length?`<p style="color:var(--ok)">Bonus: ${c.bonuses.map(x=>esc(x.label)+' +'+x.points).join(', ')}</p>`:'')+
      `<p style="color:var(--mut);font-size:12.5px">Persaingan ${c.competition_ratio}:1 &middot; batas ${c.deadline||'-'}</p>
       <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
       <a class="btn" href="${c.apply_url}" target="_blank" rel="noopener">Buka halaman apply</a>
       <button class="btn gh" onclick="track('${c.id}','applied')">Tandai sudah dilamar</button></div>`;
  } else if(tab==='desc'){
    b.innerHTML=`<p><b>Jurusan:</b> ${esc((c.majors||[]).join(', ')||'bebas')}</p>
      <p><b>Jenjang:</b> ${esc((c.levels||[]).join(', ')||'bebas')}</p>
      <p><b>Alamat:</b> ${esc(c.address||'-')}</p><pre>${esc(c.description||'(tidak ada)')}</pre>
      ${c.requirements?`<p><b>Syarat khusus</b></p><pre>${esc(c.requirements)}</pre>`:''}`;
  } else if(tab==='letter'){
    b.innerHTML=`<p style="color:var(--mut);font-size:12.5px">Sunting seperlunya sebelum dikirim.</p>
      <pre id="lt">${esc(c.letter)}</pre>
      <button class="btn" onclick="copy('lt')">Salin surat</button>`;
  } else {
    b.innerHTML=`<pre>${esc(c.checklist)}</pre>`;
  }
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  tab=t.dataset.t;document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  t.classList.add('on');render();});
function copy(id){navigator.clipboard.writeText($('#'+id).textContent);}
async function track(id,st){
  await fetch(`/api/track/${id}?status=${st}`,{method:'POST'});load();
}
['q'].forEach(i=>$('#'+i).addEventListener('input',debounce(load,280)));
['min','vd','pv','gv'].forEach(i=>$('#'+i).addEventListener('change',load));
boot();
</script></body></html>"""
