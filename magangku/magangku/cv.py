"""Bootstrap a profile from a plain-text/Markdown CV.

Deliberately dependency-free heuristics (no LLM, no PDF lib): the goal is to
give the user a *filled-in starting point* they then edit by hand, not perfect
extraction.

PDF/DOCX: convert first, e.g. `pdftotext cv.pdf cv.txt`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .profile import LEVEL_ALIASES, MAJOR_CLUSTERS

# Skill vocabulary worth detecting. Multi-word entries are matched verbatim.
SKILL_VOCAB = [
    # programming
    "python", "javascript", "typescript", "java", "kotlin", "swift", "php", "golang",
    "go", "c++", "c#", "ruby", "rust", "dart", "scala", "r",
    # web
    "html", "css", "react", "next.js", "vue", "angular", "svelte", "node.js",
    "express", "laravel", "codeigniter", "django", "flask", "fastapi", "spring boot",
    "tailwind", "bootstrap", "rest api", "graphql",
    # data
    "sql", "mysql", "postgresql", "mongodb", "sqlite", "excel", "spreadsheet",
    "power bi", "tableau", "looker", "data analysis", "data visualization",
    "machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn",
    "pandas", "numpy", "etl", "big data", "spark",
    # infra
    "git", "github", "gitlab", "docker", "kubernetes", "linux", "aws", "gcp",
    "azure", "ci/cd", "nginx", "jenkins", "terraform",
    # design
    "figma", "adobe photoshop", "photoshop", "illustrator", "canva", "ui/ux",
    "ux research", "wireframe", "prototyping", "coreldraw", "premiere pro",
    "after effects", "blender", "autocad", "solidworks", "sketchup", "revit",
    # office / business
    "microsoft office", "microsoft word", "powerpoint", "google workspace",
    "accounting", "akuntansi", "bookkeeping", "pajak", "audit", "sap",
    "digital marketing", "seo", "sem", "copywriting", "content writing",
    "social media", "public speaking", "negotiation", "customer service",
    "project management", "scrum", "agile", "notion", "jira", "trello",
    # soft skills
    "leadership", "teamwork", "komunikasi", "problem solving", "time management",
    "analytical thinking", "adaptability", "kerja tim", "kepemimpinan",
]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"(?:\+62|62|0)8[1-9][0-9]{6,11}")
GPA_RE = re.compile(r"(?:ipk|gpa|indeks prestasi)\D{0,12}([0-4][.,]\d{1,2})", re.I)
LINKEDIN_RE = re.compile(r"(?:linkedin\.com/in/)([\w-]+)", re.I)
GITHUB_RE = re.compile(r"(?:github\.com/)([\w-]+)", re.I)

UNIVERSITY_RE = re.compile(
    r"\b((?:universitas|univ\.?|institut|politeknik|sekolah tinggi|akademi|"
    r"stmik|stikom|stie|uin|iain)\s+[A-Za-z.'\- ]{3,45})",
    re.I,
)

# Words that signal the university name has ended (CVs run them together on
# one line, e.g. "Universitas Gadjah Mada dengan IPK 3.62").
_UNI_STOPWORDS = re.compile(
    r"\s+(?:dengan|dan|jurusan|program|fakultas|prodi|ipk|gpa|angkatan|tahun|"
    r"sarjana|magister|diploma|lulus|semester|di|pada|sejak)\b.*$",
    re.I,
)


def _clean_university(name: str) -> str:
    name = " ".join(name.split())
    name = _UNI_STOPWORDS.sub("", name)
    return name.strip(" .,-").title()

# City list kept small on purpose: covers the majority of Indonesian CVs.
CITIES = [
    "yogyakarta", "jogja", "sleman", "bantul", "jakarta", "bandung", "surabaya",
    "semarang", "solo", "surakarta", "medan", "makassar", "denpasar", "malang",
    "bogor", "depok", "tangerang", "bekasi", "palembang", "padang", "pekanbaru",
    "banjarmasin", "balikpapan", "samarinda", "manado", "batam", "cirebon",
    "purwokerto", "magelang", "salatiga", "kudus", "jember", "kediri",
]


def _read(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File CV tidak ditemukan: {p}")
    if p.suffix.lower() == ".pdf":
        raise ValueError(
            "File PDF belum didukung langsung.\n"
            f"Konversi dulu:  pdftotext -layout {p} cv.txt\n"
            "lalu jalankan ulang dengan --cv cv.txt"
        )
    return p.read_text(encoding="utf-8", errors="ignore")


def extract_skills(text: str) -> list[str]:
    low = text.casefold()
    tokens = set(re.findall(r"[a-z][a-z0-9+#./-]{1,}", low))
    found: list[str] = []
    for skill in SKILL_VOCAB:
        s = skill.casefold()
        hit = (s in low) if (" " in s or "/" in s or "." in s) else (s in tokens)
        if hit and skill not in found:
            found.append(skill)
    return found


def extract_majors(text: str) -> list[str]:
    low = text.casefold()
    found: list[str] = []
    for cluster, tokens in MAJOR_CLUSTERS.items():
        for token in sorted(tokens, key=len, reverse=True):
            if token in low:
                pretty = token.title()
                if pretty not in found:
                    found.append(pretty)
                break
    return found[:4]


def extract_level(text: str) -> str:
    low = text.casefold()
    pretty = {"s3": "Doktor", "s2": "Magister", "s1": "Sarjana",
              "d4": "Diploma IV", "d3": "Diploma III", "sma": "SMA/SMK sederajat"}
    for key in ("s3", "s2", "s1", "d4", "d3", "sma"):
        for token in LEVEL_ALIASES[key]:
            if re.search(rf"\b{re.escape(token)}\b", low):
                return pretty[key]
    return ""


def extract_city(text: str) -> str:
    low = text.casefold()
    best: tuple[int, str] | None = None
    for city in CITIES:
        idx = low.find(city)
        if idx >= 0 and (best is None or idx < best[0]):
            best = (idx, city)
    if not best:
        return ""
    name = best[1]
    return "Yogyakarta" if name == "jogja" else name.title()


def extract_name(text: str) -> str:
    """First plausible line: 2-4 capitalised words, no digits/@."""
    for line in text.splitlines()[:12]:
        cleaned = line.strip().strip("#*_-|").strip()
        if not (4 <= len(cleaned) <= 55):
            continue
        if any(ch.isdigit() for ch in cleaned) or "@" in cleaned:
            continue
        low = cleaned.casefold()
        if any(w in low for w in ("curriculum", "vitae", "resume", "cv", "daftar riwayat")):
            continue
        words = cleaned.split()
        if 2 <= len(words) <= 4 and all(w[:1].isupper() for w in words if w[:1].isalpha()):
            return cleaned
    return ""


def parse_cv(path: str | Path) -> dict[str, Any]:
    text = _read(path)

    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    gpa = GPA_RE.search(text)
    linkedin = LINKEDIN_RE.search(text)
    github = GITHUB_RE.search(text)
    uni = UNIVERSITY_RE.search(text)

    majors = extract_majors(text)
    return {
        "identity": {
            "name": extract_name(text),
            "email": email.group(0) if email else "",
            "phone": phone.group(0) if phone else "",
            "city": extract_city(text),
            "university": _clean_university(uni.group(1)) if uni else "",
            "level": extract_level(text),
            "gpa": gpa.group(1).replace(",", ".") if gpa else "",
            "linkedin": f"https://linkedin.com/in/{linkedin.group(1)}" if linkedin else "",
            "portfolio": f"https://github.com/{github.group(1)}" if github else "",
        },
        "majors": majors[:2],
        "adjacent_majors": majors[2:4],
        "skills": extract_skills(text),
        "_stats": {"chars": len(text), "lines": len(text.splitlines())},
    }


# Literal values shipped in profile.example.yml. If the profile still holds one
# of these, the user has not personalised the field yet, so CV data may fill it.
TEMPLATE_VALUES = {
    "", "-", "nama lengkap anda", "email@contoh.com", "08xxxxxxxxxx",
    "nama kampus", "yogyakarta", "sarjana", "3.50",
}


def merge_into_profile(
    base: dict[str, Any],
    parsed: dict[str, Any],
    *,
    overwrite_identity: bool = False,
) -> dict[str, Any]:
    """Fill gaps from the CV without clobbering values the user actually wrote.

    `overwrite_identity=True` is used when seeding a brand-new profile from the
    example template, where every value is by definition a placeholder.
    """
    out = dict(base)

    identity = dict(out.get("identity") or {})
    for key, value in (parsed.get("identity") or {}).items():
        if not value:
            continue
        current = str(identity.get(key, "")).strip()
        if overwrite_identity or current.casefold() in TEMPLATE_VALUES:
            identity[key] = value
    out["identity"] = identity

    for key in ("majors", "adjacent_majors", "skills"):
        incoming = parsed.get(key) or []
        if not incoming:
            continue
        existing = out.get(key) or []
        # Values straight out of profile.example.yml count as "not set".
        template_defaults = {
            "majors": {"teknik informatika"},
            "adjacent_majors": {"sistem informasi", "ilmu komputer"},
            "skills": {"python", "javascript", "sql", "git", "data analysis"},
        }
        is_default = {str(m).casefold() for m in existing} == template_defaults.get(key, set())
        if not existing or is_default or overwrite_identity:
            out[key] = incoming
        else:
            seen = {str(x).casefold() for x in existing}
            out[key] = existing + [x for x in incoming if str(x).casefold() not in seen]

    return out
