"""Export ranked matches to CSV / JSON / Markdown / standalone HTML."""

from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path

from .matcher import MatchResult
from .profile import Profile

VERDICT_LABEL = {
    "strong": "Sangat cocok",
    "good": "Cocok",
    "maybe": "Pertimbangkan",
    "weak": "Kurang cocok",
    "blocked": "Tersaring",
}
VERDICT_COLOR = {
    "strong": "#16a34a", "good": "#0284c7", "maybe": "#d97706",
    "weak": "#64748b", "blocked": "#dc2626",
}

CSV_FIELDS = [
    "score", "verdict", "position", "company", "city", "province", "quota",
    "registered", "competition_ratio", "acceptance_estimate", "days_left",
    "deadline", "majors", "levels", "is_government", "apply_url", "id", "reasons",
]


def _row(r: MatchResult) -> dict[str, object]:
    v = r.vacancy
    return {
        "score": r.score,
        "verdict": r.verdict,
        "position": v.position,
        "company": v.company,
        "city": v.city.title(),
        "province": v.province.title(),
        "quota": v.quota,
        "registered": v.registered,
        "competition_ratio": v.competition_ratio,
        "acceptance_estimate": v.acceptance_estimate,
        "days_left": v.days_left if v.days_left is not None else "",
        "deadline": v.deadline.isoformat() if v.deadline else "",
        "majors": "; ".join(v.majors),
        "levels": "; ".join(v.levels),
        "is_government": "ya" if v.is_government else "tidak",
        "apply_url": v.apply_url,
        "id": v.id,
        "reasons": " | ".join(r.reasons[:4]),
    }


def to_csv(results: list[MatchResult], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in results:
            writer.writerow(_row(r))
    return path


def to_json(results: list[MatchResult], path: str | Path, profile: Profile | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile": profile.summary() if profile else None,
        "count": len(results),
        "results": [r.to_dict() for r in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def to_markdown(results: list[MatchResult], path: str | Path, profile: Profile | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Hasil Pencocokan Lowongan MagangHub",
        "",
        f"_Dibuat: {datetime.now().strftime('%d %B %Y %H:%M')}_",
    ]
    if profile:
        lines.append(f"_Profil: **{profile.name or '-'}** - "
                     f"{', '.join(profile.majors) or '-'} - {profile.level or '-'}_")
    lines += ["", f"**{len(results)} lowongan** lolos filter.", "",
              "| # | Skor | Posisi | Perusahaan | Lokasi | Kuota/Pelamar | Sisa | Link |",
              "|--:|-----:|--------|-----------|--------|---------------|-----:|------|"]

    for i, r in enumerate(results, 1):
        v = r.vacancy
        days = f"{v.days_left}h" if v.days_left is not None else "-"
        lines.append(
            f"| {i} | **{r.score}** | {v.position} | {v.company} | {v.location} "
            f"| {v.quota}/{v.registered} | {days} | [buka]({v.apply_url}) |"
        )

    lines += ["", "---", "", "## Rincian"]
    for i, r in enumerate(results[:40], 1):
        v = r.vacancy
        lines += [
            "", f"### {i}. {v.position} - {v.company}",
            f"- **Skor**: {r.score}/100 ({VERDICT_LABEL.get(r.verdict, r.verdict)})",
            f"- **Lokasi**: {v.location}",
            f"- **Kuota / Pendaftar**: {v.quota} / {v.registered} "
            f"({v.competition_ratio}:1, est. {round(v.acceptance_estimate * 100)}%)",
            f"- **Batas daftar**: {v.deadline or '-'}",
            f"- **Jurusan**: {', '.join(v.majors) or 'bebas'}",
            f"- **Jenjang**: {', '.join(v.levels) or 'bebas'}",
            f"- **Alasan**: {'; '.join(r.reasons[:5]) or '-'}",
            f"- **Apply**: {v.apply_url}",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def to_html(results: list[MatchResult], path: str | Path, profile: Profile | None = None) -> Path:
    """Self-contained HTML report - openable offline, shareable as one file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    e = html.escape

    cards = []
    for i, r in enumerate(results, 1):
        v = r.vacancy
        color = VERDICT_COLOR.get(r.verdict, "#64748b")
        reasons = "".join(f"<li>{e(x)}</li>" for x in r.reasons[:5])
        majors = ", ".join(v.majors[:6]) or "bebas"
        days = (f'<span class="chip warn">{v.days_left} hari lagi</span>'
                if v.days_left is not None and v.days_left <= 7
                else (f'<span class="chip">{v.days_left} hari lagi</span>'
                      if v.days_left is not None else ""))
        gov = '<span class="chip gov">Pemerintah</span>' if v.is_government else ""
        cards.append(f"""
      <article class="card" data-score="{r.score}" data-text="{e((v.position + ' ' + v.company + ' ' + v.location).casefold())}">
        <div class="rank">#{i}</div>
        <div class="score" style="--c:{color}">{r.score}<small>/100</small></div>
        <div class="main">
          <h3>{e(v.position)}</h3>
          <p class="co">{e(v.company)} &middot; {e(v.location)}</p>
          <div class="chips">
            <span class="chip">Kuota {v.quota}</span>
            <span class="chip">{v.registered} pelamar</span>
            <span class="chip">{v.competition_ratio}:1</span>
            <span class="chip ok">est. {round(v.acceptance_estimate * 100)}%</span>
            {days}{gov}
          </div>
          <p class="mj"><b>Jurusan:</b> {e(majors)}</p>
          <ul class="why">{reasons}</ul>
        </div>
        <a class="btn" href="{e(v.apply_url)}" target="_blank" rel="noopener">Buka &rarr;</a>
      </article>""")

    prof_line = ""
    if profile:
        prof_line = (f"{e(profile.name or '-')} &middot; {e(', '.join(profile.majors) or '-')} "
                     f"&middot; {e(profile.level or '-')}")

    doc = f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MagangKu - Hasil Pencocokan</title>
<style>
:root{{--bg:#0b1220;--card:#141d31;--line:#243149;--tx:#e6edf7;--mut:#93a4bf;--ac:#38bdf8}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:24px}}
.wrap{{max-width:1080px;margin:0 auto}}
header{{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:20px}}
h1{{margin:0 0 6px;font-size:22px;color:var(--ac)}}
.sub{{color:var(--mut);font-size:13px}}
.tools{{display:flex;gap:10px;margin:16px 0;flex-wrap:wrap}}
input,select{{background:var(--card);border:1px solid var(--line);color:var(--tx);padding:10px 12px;border-radius:8px;font-size:14px}}
input{{flex:1;min-width:220px}}
.card{{display:grid;grid-template-columns:44px 78px 1fr auto;gap:14px;align-items:start;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:10px}}
.rank{{color:var(--mut);font-size:13px;padding-top:6px}}
.score{{font-size:26px;font-weight:700;color:var(--c);line-height:1.1}}
.score small{{font-size:11px;color:var(--mut);font-weight:400}}
h3{{margin:0 0 3px;font-size:16px}}
.co{{margin:0 0 8px;color:var(--mut);font-size:13px}}
.chips{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}}
.chip{{background:#1d2942;border:1px solid var(--line);color:var(--mut);font-size:11px;padding:3px 8px;border-radius:99px}}
.chip.ok{{color:#4ade80;border-color:#14532d}}
.chip.warn{{color:#fbbf24;border-color:#78350f}}
.chip.gov{{color:#c084fc;border-color:#581c87}}
.mj{{margin:0 0 6px;font-size:12.5px;color:var(--mut)}}
.why{{margin:0;padding-left:16px;color:var(--mut);font-size:12.5px}}
.btn{{align-self:center;background:var(--ac);color:#06263a;font-weight:700;text-decoration:none;padding:9px 14px;border-radius:8px;font-size:13px;white-space:nowrap}}
.btn:hover{{filter:brightness(1.1)}}
@media(max-width:720px){{.card{{grid-template-columns:1fr;gap:8px}}.btn{{justify-self:start}}}}
</style></head><body><div class="wrap">
<header><h1>MagangKu &mdash; Hasil Pencocokan</h1>
<div class="sub">{prof_line}</div>
<div class="sub">{len(results)} lowongan &middot; dibuat {datetime.now().strftime('%d %b %Y %H:%M')}</div></header>
<div class="tools">
  <input id="q" placeholder="Cari posisi / perusahaan / kota...">
  <select id="min"><option value="0">Semua skor</option><option value="45">&ge; 45</option>
  <option value="60">&ge; 60</option><option value="75">&ge; 75</option></select>
</div>
<div id="list">{''.join(cards)}</div>
<p class="sub" style="margin-top:20px">Sumber: MagangHub Kemnaker. Skor dihitung lokal dari profil Anda &mdash; tetap baca detail resmi sebelum melamar.</p>
</div>
<script>
const q=document.getElementById('q'),m=document.getElementById('min'),cards=[...document.querySelectorAll('.card')];
function f(){{const t=q.value.toLowerCase().trim(),s=parseFloat(m.value);
cards.forEach(c=>{{const ok=c.dataset.text.includes(t)&&parseFloat(c.dataset.score)>=s;c.style.display=ok?'grid':'none';}});}}
q.addEventListener('input',f);m.addEventListener('change',f);
</script></body></html>"""
    path.write_text(doc, encoding="utf-8")
    return path


def export_all(results: list[MatchResult], out_dir: str | Path,
               profile: Profile | None = None) -> dict[str, Path]:
    out_dir = Path(out_dir)
    return {
        "csv": to_csv(results, out_dir / "matches.csv"),
        "json": to_json(results, out_dir / "matches.json", profile),
        "markdown": to_markdown(results, out_dir / "matches.md", profile),
        "html": to_html(results, out_dir / "matches.html", profile),
    }
