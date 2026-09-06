"""Generate a tailored cover letter / motivation letter per vacancy.

Template-based and fully offline. Every letter references concrete details from
the vacancy (position, company, matching skills, matching major) so it never
reads like a mass-produced form.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .matcher import MatchResult
from .models import Vacancy
from .profile import Profile

MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def _date_id(d: date | None = None) -> str:
    d = d or date.today()
    return f"{d.day} {MONTHS_ID[d.month - 1]} {d.year}"


def _slug(text: str, maxlen: int = 48) -> str:
    text = re.sub(r"[^\w\s-]", "", (text or "").casefold())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:maxlen] or "lowongan"


# Skills whose conventional spelling is not simple title-case.
_SKILL_CASING = {
    "sql": "SQL", "html": "HTML", "css": "CSS", "php": "PHP", "aws": "AWS",
    "gcp": "GCP", "api": "API", "rest api": "REST API", "ui/ux": "UI/UX",
    "ci/cd": "CI/CD", "seo": "SEO", "sem": "SEM", "sap": "SAP", "etl": "ETL",
    "power bi": "Power BI", "next.js": "Next.js", "node.js": "Node.js",
    "vue": "Vue", "react": "React", "figma": "Figma", "docker": "Docker",
    "git": "Git", "github": "GitHub", "gitlab": "GitLab", "linux": "Linux",
    "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript",
    "java": "Java", "golang": "Go", "kotlin": "Kotlin", "swift": "Swift",
    "excel": "Excel", "tableau": "Tableau", "django": "Django", "flask": "Flask",
    "fastapi": "FastAPI", "laravel": "Laravel", "tailwind": "Tailwind",
    "pandas": "Pandas", "numpy": "NumPy", "pytorch": "PyTorch",
    "tensorflow": "TensorFlow", "kubernetes": "Kubernetes",
}


def _pretty_skill(skill: str) -> str:
    s = skill.casefold().strip()
    if s in _SKILL_CASING:
        return _SKILL_CASING[s]
    # Leave already-capitalised input alone; otherwise title-case it.
    return skill if skill != s else s.title()


def _matching_skills(profile: Profile, vacancy: Vacancy, limit: int = 5) -> list[str]:
    haystack = vacancy.search_text
    tokens = set(re.findall(r"[a-z][a-z0-9+#.]{1,}", haystack))
    hits = []
    for skill in profile.skills:
        s = skill.casefold()
        hit = (s in haystack) if (" " in s or "-" in s) else (s in tokens)
        if hit:
            hits.append(skill)
    if not hits:
        hits = profile.skills[:limit]
    return [_pretty_skill(h) for h in hits[:limit]]


def _matching_major(profile: Profile, vacancy: Vacancy) -> str:
    if profile.majors:
        return profile.majors[0]
    return vacancy.majors[0] if vacancy.majors else "bidang terkait"


# --------------------------------------------------------------------------- #
def build_letter(profile: Profile, result: MatchResult, *, language: str | None = None) -> str:
    v = result.vacancy
    lang = (language or (profile.letter or {}).get("language") or "id").lower()
    return _english(profile, v, result) if lang.startswith("en") else _indonesian(profile, v, result)


def _indonesian(profile: Profile, v: Vacancy, result: MatchResult) -> str:
    letter_cfg = profile.letter or {}
    name = profile.name or "[Nama Anda]"
    major = _matching_major(profile, v)
    skills = _matching_skills(profile, v)
    skills_text = ", ".join(skills[:-1]) + (f", dan {skills[-1]}" if len(skills) > 1 else (skills[0] if skills else ""))
    city = letter_cfg.get("closing_city") or profile.home_city or "Indonesia"

    highlights = letter_cfg.get("highlights") or []
    highlight_block = "\n".join(f"- {h}" for h in highlights) if highlights else ""

    edu_bits = []
    if profile.level:
        edu_bits.append(profile.level)
    if profile.majors:
        edu_bits.append(profile.majors[0])
    if profile.university:
        edu_bits.append(profile.university)
    edu = " ".join(edu_bits) if edu_bits else "mahasiswa"
    gpa_text = f" dengan IPK {profile.gpa}" if profile.gpa else ""

    tone = (letter_cfg.get("tone") or "profesional").casefold()
    opener = {
        "antusias": (
            f"Dengan penuh antusias saya mengajukan lamaran untuk posisi "
            f"<b>{v.position}</b> di {v.company}."
        ),
        "ringkas": (
            f"Saya bermaksud melamar posisi <b>{v.position}</b> di {v.company}."
        ),
    }.get(tone, (
        f"Melalui surat ini saya bermaksud mengajukan lamaran untuk posisi "
        f"<b>{v.position}</b> di {v.company} yang saya temukan melalui platform "
        f"MagangHub Kemnaker."
    )).replace("<b>", "").replace("</b>", "")

    contact = " | ".join(filter(None, [profile.email, profile.phone]))
    deadline_note = (
        f"\nSaya memahami batas pendaftaran posisi ini adalah "
        f"{v.deadline.strftime('%d/%m/%Y')}, dan saya siap mengikuti proses seleksi "
        f"sesuai jadwal yang ditentukan."
        if v.deadline else ""
    )

    body = f"""{_date_id()}

Kepada Yth.
Tim Rekrutmen {v.company}
{v.address or v.location}

Perihal: Lamaran Magang - {v.position}

Dengan hormat,

{opener}

Saya {name}, {edu}{gpa_text}. Latar belakang saya di bidang {major} membuat saya merasa posisi ini sangat relevan dengan kompetensi maupun rencana pengembangan karier saya.

Beberapa kemampuan yang saya nilai relevan dengan kebutuhan posisi ini:
{("- Penguasaan " + skills_text + ".") if skills_text else "- Kemauan belajar cepat dan disiplin dalam bekerja."}
{highlight_block}

Saya tertarik pada posisi ini karena {_interest_reason(v)}. Saya yakin kesempatan magang di {v.company} akan menjadi sarana yang tepat untuk menerapkan ilmu yang saya pelajari sekaligus berkontribusi nyata pada tim.
{deadline_note}

Bersama surat ini saya lampirkan CV sebagai bahan pertimbangan. Saya sangat terbuka untuk mengikuti wawancara atau tahapan seleksi lainnya sesuai waktu yang Bapak/Ibu tentukan.

Atas perhatian dan kesempatan yang diberikan, saya ucapkan terima kasih.

Hormat saya,

{name}
{contact}
{city}, {_date_id()}
"""
    return _tidy(body)


def _english(profile: Profile, v: Vacancy, result: MatchResult) -> str:
    name = profile.name or "[Your Name]"
    skills = _matching_skills(profile, v)
    skills_text = ", ".join(skills)
    contact = " | ".join(filter(None, [profile.email, profile.phone]))
    edu = " ".join(filter(None, [profile.level, profile.majors[0] if profile.majors else "",
                                 profile.university]))
    highlights = (profile.letter or {}).get("highlights") or []
    highlight_block = "\n".join(f"- {h}" for h in highlights)

    body = f"""{date.today().strftime('%d %B %Y')}

Recruitment Team
{v.company}
{v.address or v.location}

Subject: Internship Application - {v.position}

Dear Hiring Team,

I am writing to apply for the {v.position} internship at {v.company}, which I found through the Kemnaker MagangHub platform.

I am {name}, {edu or 'a student'}. My academic background aligns closely with the requirements of this role.

Relevant strengths I bring:
{("- Working knowledge of " + skills_text + ".") if skills_text else "- Fast learner with strong discipline."}
{highlight_block}

I am confident this internship will let me apply what I have learned while making a genuine contribution to your team.

My CV is attached for your consideration. I would welcome the opportunity to discuss my application at your convenience.

Thank you for your time.

Sincerely,

{name}
{contact}
"""
    return _tidy(body)


# Fragments that read badly when spliced into a sentence ("...karena X...").
_BAD_LEAD = re.compile(
    r"^\s*(?:menguasai|memiliki|mampu|dapat|bisa|diutamakan|persyaratan|syarat|"
    r"kualifikasi|keahlian|kriteria|deskripsi|tugas|job\s?desc|requirement)\b",
    re.I,
)


def _interest_reason(v: Vacancy) -> str:
    """Pick a clause from the job description that reads naturally after 'karena'."""
    desc = (v.description or "").strip()
    if desc:
        for sentence in re.split(r"(?<=[.;])\s+|\n", desc):
            s = sentence.strip()
            # Drop list markers: "- ", "* ", "1. ", "a) " ...
            s = re.sub(r"^[\-\*\u2022\u2013\u2014]+\s*", "", s)
            s = re.sub(r"^\(?[0-9a-zA-Z]{1,2}[.)]\s+", "", s)
            s = s.strip().rstrip(".;: ")
            if not (25 <= len(s) <= 170):
                continue
            # "HTML & CSS: penguasaan dasar..." -> label:value, reads badly.
            if ":" in s or s.endswith(":"):
                continue
            if _BAD_LEAD.search(s) or s.count(",") > 5:
                continue
            if sum(ch.isdigit() for ch in s) > len(s) * 0.2:
                continue
            if not re.match(r"^[A-Za-z\u00c0-\u024f]", s):
                continue
            return (f"lingkup pekerjaannya - {s[0].lower()}{s[1:]} - "
                    f"sejalan dengan bidang yang saya tekuni")
    if v.is_government:
        return ("saya ingin memahami langsung tata kelola dan pelayanan publik "
                "di lingkungan instansi pemerintah")
    return (f"{v.company} memiliki lingkungan kerja yang saya nilai tepat "
            f"untuk mengembangkan kompetensi saya")


def _tidy(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip() + "\n"


# --------------------------------------------------------------------------- #
def write_letter(
    profile: Profile,
    result: MatchResult,
    out_dir: str | Path,
    *,
    language: str | None = None,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    v = result.vacancy
    filename = f"{_slug(v.company, 32)}_{_slug(v.position, 40)}_{v.id[:8]}.txt"
    path = out_dir / filename
    path.write_text(build_letter(profile, result, language=language), encoding="utf-8")
    return path


def build_checklist(profile: Profile, result: MatchResult) -> str:
    """A short pre-apply briefing the user reads before hitting submit."""
    v = result.vacancy
    lines = [
        f"# Checklist Lamaran - {v.position}",
        "",
        f"**Perusahaan** : {v.company}",
        f"**Lokasi**     : {v.location}",
        f"**Kuota**      : {v.quota} | **Pendaftar**: {v.registered} "
        f"({v.competition_ratio}:1, est. diterima {round(v.acceptance_estimate * 100)}%)",
        f"**Batas daftar**: {v.deadline or 'tidak disebutkan'}"
        + (f" ({v.days_left} hari lagi)" if v.days_left is not None else ""),
        f"**Skor cocok** : {result.score}/100 ({result.verdict})",
        f"**Link**       : {v.apply_url}",
        "",
        "## Kenapa cocok",
    ]
    lines += [f"- {r}" for r in result.reasons[:6]] or ["- (tidak ada catatan)"]
    lines += [
        "",
        "## Sebelum submit, pastikan",
        "- [ ] CV terbaru sudah diunggah di profil MagangHub",
        "- [ ] Surat lamaran sudah dibaca ulang & disesuaikan",
        f"- [ ] Jurusan yang diminta ({', '.join(v.majors[:4]) or 'bebas'}) sesuai",
        f"- [ ] Jenjang ({', '.join(v.levels) or 'bebas'}) sesuai",
        "- [ ] Dokumen pendukung (transkrip, KTP, surat kampus) siap",
        "- [ ] Sudah cek ulang deskripsi & lokasi penempatan",
        "",
        "## Deskripsi posisi",
        (v.description or "(tidak tersedia)")[:1200],
    ]
    if v.requirements:
        lines += ["", "## Syarat khusus", v.requirements[:800]]
    return "\n".join(lines) + "\n"
