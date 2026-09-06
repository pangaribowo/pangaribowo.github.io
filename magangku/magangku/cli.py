"""MagangKu command-line interface.

    magangku doctor                 # cek kesiapan sistem
    magangku profile init|show|from-cv
    magangku scrape --source fixtures|live
    magangku match --top 20
    magangku apply --top 5          # siapkan berkas (assisted, tidak auto-submit)
    magangku track / status
    magangku watch                  # deteksi lowongan baru + notifikasi
    magangku serve                  # dashboard web
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .cv import merge_into_profile, parse_cv
from .letter import build_checklist, write_letter
from .matcher import Matcher
from .models import Vacancy
from .notify import dispatch
from .profile import Profile, default_profile_path
from .report import VERDICT_LABEL, export_all
from .session import HELP_TEXT, PROFILE_ENDPOINTS, Session, SessionClient, redact
from .sync import (
    apply_to_profile,
    load_profile_dict,
    map_kemnaker_profile,
    write_profile_dict,
)
from .scraper import (
    MagangHubScraper,
    ScrapeError,
    fixtures_dir,
    load_fixtures,
    load_from_dir,
    load_provinces,
)
from .storage import VALID_STATUSES, Store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "magangku.db"
DEFAULT_OUT = ROOT / "out"
RAW_DIR = ROOT / "data" / "raw"

# --------------------------------------------------------------------------- #
# Pretty output (rich if available, plain otherwise)
# --------------------------------------------------------------------------- #
try:
    from rich.console import Console
    from rich.table import Table

    _console: "Console | None" = Console()
except Exception:  # pragma: no cover
    _console = None


def say(msg: str = "", style: str = "") -> None:
    if _console and style:
        _console.print(msg, style=style)
    elif _console:
        _console.print(msg)
    else:
        print(msg)


def ok(msg: str) -> None:
    say(f"[OK] {msg}", "green")


def warn(msg: str) -> None:
    say(f"[!] {msg}", "yellow")


def err(msg: str) -> None:
    say(f"[X] {msg}", "bold red")


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# --------------------------------------------------------------------------- #
def get_profile(args: argparse.Namespace) -> Profile:
    path = default_profile_path(getattr(args, "profile", None))
    try:
        profile = Profile.load(path)
    except FileNotFoundError as exc:
        err(str(exc))
        sys.exit(1)
    if path.name == "profile.example.yml":
        warn("Memakai profile.example.yml (contoh). Jalankan `magangku profile init` "
             "untuk membuat profil pribadi Anda.")
    return profile


def get_store(args: argparse.Namespace) -> Store:
    return Store(getattr(args, "db", None) or DEFAULT_DB)


def load_vacancies(args: argparse.Namespace, store: Store) -> list[Vacancy]:
    """Resolve the data source for read-only commands."""
    source = getattr(args, "source", "db")
    if source == "fixtures":
        return load_fixtures()
    if source == "dir":
        return load_from_dir(Path(args.data_dir))
    vacancies = store.all_vacancies()
    if not vacancies:
        warn("Database masih kosong - memakai data contoh (fixtures).")
        warn("Jalankan `magangku scrape` dulu untuk data terbaru.")
        return load_fixtures()
    return vacancies


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_doctor(args: argparse.Namespace) -> int:
    say("\n=== MagangKu :: Pemeriksaan Sistem ===\n", "bold cyan")
    problems = 0

    say(f"Python           : {sys.version.split()[0]}")
    for mod in ("httpx", "yaml", "fastapi", "rich"):
        try:
            __import__(mod)
            say(f"  {mod:<14} : terpasang")
        except ImportError:
            say(f"  {mod:<14} : TIDAK ADA", "red")
            problems += 1

    prof_path = default_profile_path(getattr(args, "profile", None))
    say(f"\nProfil           : {prof_path}")
    if prof_path.name == "profile.example.yml":
        warn("  Belum ada profile.yml pribadi (`magangku profile init`)")
    try:
        profile = Profile.load(prof_path)
        for w in profile.validate():
            warn(f"  {w}")
        ok(f"  Profil terbaca: {profile.name or '(tanpa nama)'}")
    except Exception as exc:  # noqa: BLE001
        err(f"  Gagal baca profil: {exc}")
        problems += 1

    fx = fixtures_dir()
    count = len(list(fx.glob("*.json"))) if fx.exists() else 0
    say(f"\nData contoh      : {count} file di {fx}")
    if count == 0:
        warn("  Fixtures hilang - mode offline tidak akan jalan")

    db = Path(getattr(args, "db", None) or DEFAULT_DB)
    if db.exists():
        stats = Store(db).stats()
        ok(f"Database         : {db.name} ({stats['total_vacancies']} lowongan, "
           f"{stats['open_vacancies']} masih buka)")
    else:
        say(f"Database         : belum dibuat ({db.name})")

    say("\nKoneksi ke MagangHub...")
    try:
        MagangHubScraper(max_retries=1, timeout=12).fetch_page(page=1, limit=1)
        ok("  API Kemnaker dapat dihubungi - mode live siap")
    except ScrapeError as exc:
        warn(f"  Tidak bisa terhubung: {str(exc).splitlines()[0]}")
        say("  -> Jalankan `magangku probe` untuk melihat endpoint mana yang hidup.", "dim")
        say("  -> Atau gunakan `--source fixtures` untuk mode offline.", "dim")

    env = ROOT / ".env"
    say(f"\n.env             : {'ada' if env.exists() else 'belum ada (opsional)'}")
    if os.getenv("NTFY_TOPIC"):
        ok("  Notifikasi ntfy aktif")
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        ok("  Notifikasi Telegram aktif")

    say("")
    if problems:
        err(f"Ditemukan {problems} masalah. Jalankan: pip install -r requirements.txt")
        return 1
    ok("Sistem siap dipakai.")
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    target = ROOT / "profile.yml"

    if args.action == "init":
        if target.exists() and not args.force:
            warn(f"{target.name} sudah ada. Pakai --force untuk menimpa.")
            return 1
        shutil.copy(ROOT / "profile.example.yml", target)
        ok(f"Profil dibuat: {target}")
        say("Silakan edit bagian identity, majors, skills, dan location.")
        if args.cv:
            # Freshly copied from the template -> every value is a placeholder.
            args.action = "from-cv"
            args._seeding = True
            return cmd_profile(args)
        return 0

    if args.action == "from-cv":
        if not args.cv:
            err("Sertakan --cv path/ke/cv.txt")
            return 1
        try:
            parsed = parse_cv(args.cv)
        except (FileNotFoundError, ValueError) as exc:
            err(str(exc))
            return 1

        base: dict = {}
        seeding = bool(getattr(args, "_seeding", False))
        if target.exists():
            base = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        else:
            base = yaml.safe_load((ROOT / "profile.example.yml").read_text(encoding="utf-8")) or {}
            seeding = True

        merged = merge_into_profile(base, parsed, overwrite_identity=seeding)
        target.write_text(
            yaml.safe_dump(merged, allow_unicode=True, sort_keys=False, width=88),
            encoding="utf-8",
        )
        ident = parsed["identity"]
        ok(f"Profil diperbarui dari CV -> {target}")
        say(f"  Nama     : {ident['name'] or '(tidak terdeteksi)'}")
        say(f"  Email    : {ident['email'] or '-'}")
        say(f"  Kampus   : {ident['university'] or '-'}")
        say(f"  Jenjang  : {ident['level'] or '-'}")
        say(f"  Jurusan  : {', '.join(parsed['majors']) or '-'}")
        say(f"  Skill    : {len(parsed['skills'])} terdeteksi -> "
            f"{', '.join(parsed['skills'][:10])}")
        warn("Periksa & rapikan hasilnya secara manual - ini hanya tebakan otomatis.")
        return 0

    # show
    profile = get_profile(args)
    summary = profile.summary()
    say("\n=== Profil Aktif ===\n", "bold cyan")
    for key, value in summary.items():
        if key == "weights":
            say(f"{key:<12}: " + ", ".join(f"{k}={v:.0%}" for k, v in value.items()))
        else:
            say(f"{key:<12}: {value}")
    warnings = profile.validate()
    if warnings:
        say("")
        for w in warnings:
            warn(w)
    else:
        say("")
        ok("Profil lengkap.")
    return 0


def cmd_scrape(args: argparse.Namespace) -> int:
    store = get_store(args)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if args.source == "fixtures":
        say("Memuat data contoh (offline)...")
        vacancies = load_fixtures()
    elif args.source == "dir":
        say(f"Memuat data dari {args.data_dir} ...")
        vacancies = load_from_dir(Path(args.data_dir))
    else:
        scraper = MagangHubScraper(delay=args.delay)
        province = args.province
        say(f"Mengambil data dari MagangHub Kemnaker"
            f"{f' (provinsi {province})' if province else ''}...")

        def progress(page: int, total_pages: int, total_items: int) -> None:
            say(f"  halaman {page}/{total_pages or '?'} (total {total_items} lowongan)", "dim")

        try:
            vacancies = scraper.scrape(
                limit=args.limit,
                max_pages=args.max_pages,
                province=province,
                raw_dir=RAW_DIR if args.save_raw else None,
                on_page=progress,
            )
        except ScrapeError as exc:
            err(str(exc))
            return 2

    if not vacancies:
        warn("Tidak ada lowongan yang terbaca.")
        return 1

    result = store.upsert_many(vacancies)
    store.record_run(args.source, len(vacancies), len(result["new"]), started)

    ok(f"{len(vacancies)} lowongan tersimpan ke {store.path.name}")
    say(f"   Baru       : {len(result['new'])}")
    say(f"   Berubah    : {len(result['changed'])}")
    if result["changed"] and args.verbose:
        for c in result["changed"][:10]:
            say(f"     - {c['position'][:44]}: {c['registered_before']} -> "
                f"{c['registered_after']} pelamar", "dim")
    return 0


def _print_table(results, profile: Profile, limit: int) -> None:
    if _console:
        table = Table(title=f"Top {min(limit, len(results))} lowongan untuk "
                            f"{profile.name or 'Anda'}", header_style="bold cyan")
        table.add_column("#", justify="right", width=3)
        table.add_column("Skor", justify="right", width=5)
        table.add_column("Posisi", overflow="fold", max_width=34)
        table.add_column("Perusahaan", overflow="fold", max_width=26)
        table.add_column("Lokasi", max_width=18)
        table.add_column("Kuota", justify="right", width=6)
        table.add_column("Saing", justify="right", width=6)
        table.add_column("Sisa", justify="right", width=5)

        for i, r in enumerate(results[:limit], 1):
            v = r.vacancy
            color = {"strong": "green", "good": "cyan",
                     "maybe": "yellow"}.get(r.verdict, "white")
            table.add_row(
                str(i), f"[{color}]{r.score:.0f}[/{color}]", v.position, v.company,
                v.location.split(",")[0].title(), str(v.quota),
                f"{v.competition_ratio:g}:1",
                f"{v.days_left}h" if v.days_left is not None else "-",
            )
        _console.print(table)
    else:
        for i, r in enumerate(results[:limit], 1):
            v = r.vacancy
            print(f"{i:>3}. [{r.score:>5.1f}] {v.position[:40]:<40} | "
                  f"{v.company[:26]:<26} | {v.location[:20]}")


def cmd_match(args: argparse.Namespace) -> int:
    profile = get_profile(args)
    store = get_store(args)
    vacancies = load_vacancies(args, store)

    matcher = Matcher(profile)
    results = matcher.rank(
        vacancies,
        include_blocked=args.include_blocked,
        min_score=args.min_score,
        limit=args.top if args.top > 0 else None,
    )

    total = len(vacancies)
    say(f"\nMenilai {total} lowongan terhadap profil "
        f"'{profile.name or 'tanpa nama'}'...\n", "bold")

    if not results:
        warn("Tidak ada lowongan yang lolos filter.")
        # Explain *why* rather than leaving the user guessing.
        from collections import Counter

        counter: Counter[str] = Counter()
        for v in vacancies:
            for b in matcher.blockers_for(v):
                counter[b.split("(")[0].strip()] += 1
        if counter:
            say("\nPenyebab utama lowongan tersaring:")
            for reason, n in counter.most_common(5):
                say(f"   {n:>4}x  {reason}")
        if args.min_score > 0:
            say(f"\n--min-score {args.min_score:g} mungkin terlalu tinggi.")
        say("\nSaran: longgarkan `filters` di profile.yml, atau jalankan "
            "`magangku match --include-blocked` untuk melihat semuanya.")
        return 0

    _print_table(results, profile, args.top if args.top > 0 else len(results))

    buckets: dict[str, int] = {}
    for r in results:
        buckets[r.verdict] = buckets.get(r.verdict, 0) + 1
    say("\nRingkasan: " + " | ".join(
        f"{VERDICT_LABEL.get(k, k)}: {v}" for k, v in sorted(buckets.items())))

    if args.explain:
        say("\n=== Rincian skor ===", "bold cyan")
        for i, r in enumerate(results[:args.explain], 1):
            v = r.vacancy
            say(f"\n{i}. {v.position} - {v.company}  [{r.score}/100]", "bold")
            for c in sorted(r.components, key=lambda x: -x.contribution):
                bar = "#" * int(c.score * 12)
                say(f"   {c.key:<12} {c.score:>5.2f} x{c.weight:<5.2f} "
                    f"= {c.contribution * 100:>5.1f}  {bar:<12} {c.reason}", "dim")
            for label, pts in r.bonuses:
                say(f"   bonus        +{pts:<21} {label}", "dim")
            say(f"   -> {v.apply_url}", "dim")

    if args.export:
        out_dir = Path(args.out or DEFAULT_OUT)
        paths = export_all(results, out_dir, profile)
        say("")
        ok(f"Laporan diekspor ke {out_dir}/")
        for kind, path in paths.items():
            say(f"   {kind:<9}: {path.name}")
        if args.open:
            webbrowser.open(paths["html"].resolve().as_uri())
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    """Assisted apply: prepare everything, then hand control to the user."""
    profile = get_profile(args)
    store = get_store(args)
    vacancies = load_vacancies(args, store)

    matcher = Matcher(profile)
    results = matcher.rank(vacancies, min_score=args.min_score, limit=args.top)

    if not results:
        warn("Tidak ada lowongan yang memenuhi kriteria.")
        return 0

    out_dir = Path(args.out or DEFAULT_OUT) / "lamaran"
    out_dir.mkdir(parents=True, exist_ok=True)

    say("\n=== MODE ASSISTED APPLY ===", "bold cyan")
    say("Sistem menyiapkan berkas; pengiriman tetap Anda lakukan sendiri "
        "di situs resmi.\n", "dim")

    prepared = []
    for i, r in enumerate(results, 1):
        v = r.vacancy
        letter_path = write_letter(profile, r, out_dir, language=args.lang)
        checklist_path = out_dir / f"{letter_path.stem}_checklist.md"
        checklist_path.write_text(build_checklist(profile, r), encoding="utf-8")

        store.track(v.id, status="letter_ready", score=r.score,
                    letter_path=str(letter_path))
        prepared.append((r, letter_path, checklist_path))

        say(f"{i}. [{r.score:>5.1f}] {v.position} - {v.company}", "bold")
        say(f"   Lokasi   : {v.location}")
        say(f"   Peluang  : {v.registered}/{v.quota} pelamar "
            f"({round(v.acceptance_estimate * 100)}% est.)")
        say(f"   Surat    : {letter_path.relative_to(ROOT)}", "dim")
        say(f"   Checklist: {checklist_path.relative_to(ROOT)}", "dim")
        say(f"   Apply di : {v.apply_url}", "cyan")
        say("")

    index = out_dir / "index.md"
    lines = ["# Daftar Lamaran Siap Kirim", "",
             f"_Dibuat {datetime.now().strftime('%d %B %Y %H:%M')}_", ""]
    for i, (r, lp, cp) in enumerate(prepared, 1):
        v = r.vacancy
        lines += [
            f"## {i}. {v.position} - {v.company}",
            f"- Skor: **{r.score}/100** ({VERDICT_LABEL.get(r.verdict, r.verdict)})",
            f"- Batas daftar: {v.deadline or '-'}",
            f"- Surat: `{lp.name}`",
            f"- Checklist: `{cp.name}`",
            f"- Apply: {v.apply_url}",
            f"- Tandai selesai: `magangku track {v.id} --status applied`",
            "",
        ]
    index.write_text("\n".join(lines), encoding="utf-8")

    ok(f"{len(prepared)} berkas lamaran siap di {out_dir}/")
    say("\nLangkah berikutnya:")
    say("  1. Baca & sunting surat di folder tersebut")
    say("  2. Buka link apply, tempel surat, kirim manual")
    say("  3. Catat: magangku track <id> --status applied")

    if args.open and prepared:
        webbrowser.open(prepared[0][0].vacancy.apply_url)
    return 0


def cmd_track(args: argparse.Namespace) -> int:
    store = get_store(args)
    try:
        store.track(args.vacancy_id, status=args.status, note=args.note or "")
    except ValueError as exc:
        err(str(exc))
        return 1
    vacancy = store.get(args.vacancy_id)
    label = f"{vacancy.position} - {vacancy.company}" if vacancy else args.vacancy_id
    ok(f"Status '{args.status}' disimpan untuk: {label}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    store = get_store(args)
    stats = store.stats()
    say("\n=== Status MagangKu ===\n", "bold cyan")
    say(f"Lowongan tersimpan : {stats['total_vacancies']}")
    say(f"Masih buka         : {stats['open_vacancies']}")
    if stats["last_run"]:
        run = stats["last_run"]
        say(f"Scrape terakhir    : {run['finished_at']} "
            f"({run['total']} lowongan, {run['new_count']} baru, sumber {run['source']})")

    apps = store.applications(args.filter_status)
    if not apps:
        say("\nBelum ada lamaran yang dicatat.")
        say("Jalankan `magangku apply --top 5` untuk menyiapkan berkas.")
        return 0

    say(f"\nLamaran ({len(apps)}):")
    if _console:
        table = Table(header_style="bold cyan")
        for col in ("Status", "Skor", "Posisi", "Perusahaan", "Batas", "Diperbarui"):
            table.add_column(col, overflow="fold")
        for a in apps:
            table.add_row(
                a["status"], f"{a['score']:.0f}" if a["score"] else "-",
                (a["position"] or "-")[:36], (a["company"] or "-")[:24],
                a["deadline"] or "-", (a["updated_at"] or "")[:10],
            )
        _console.print(table)
    else:
        for a in apps:
            print(f"  [{a['status']:<12}] {(a['position'] or '-')[:40]} "
                  f"- {(a['company'] or '-')[:26]}")

    counts = stats["applications"]
    if counts:
        say("\nRingkasan: " + " | ".join(f"{k}: {v}" for k, v in counts.items()))
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Scrape, detect brand-new vacancies, notify if they score well."""
    profile = get_profile(args)
    store = get_store(args)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if args.source == "fixtures":
        vacancies = load_fixtures()
    else:
        try:
            vacancies = MagangHubScraper(delay=args.delay).scrape(
                limit=args.limit, max_pages=args.max_pages, province=args.province
            )
        except ScrapeError as exc:
            err(str(exc))
            return 2

    result = store.upsert_many(vacancies)
    store.record_run(f"watch:{args.source}", len(vacancies), len(result["new"]), started)

    new_ids = set(result["new"])
    new_vacancies = [v for v in vacancies if v.id in new_ids]
    say(f"Total {len(vacancies)} lowongan, {len(new_vacancies)} baru.")

    if not new_vacancies:
        ok("Tidak ada lowongan baru.")
        return 0

    matcher = Matcher(profile)
    min_score = args.min_score if args.min_score > 0 else float(
        (profile.notify or {}).get("min_score", 70))
    matches = matcher.rank(new_vacancies, min_score=min_score)

    if not matches:
        say(f"Ada {len(new_vacancies)} lowongan baru, tapi tidak ada yang "
            f"melewati skor {min_score:g}.")
        return 0

    ok(f"{len(matches)} lowongan baru cocok (skor >= {min_score:g}):")
    _print_table(matches, profile, 10)

    channels = args.channel or (profile.notify or {}).get("channels") or ["console"]
    if (profile.notify or {}).get("enabled", False) or args.channel:
        say("")
        for channel, status in dispatch(
            matches, channels, title=f"{len(matches)} lowongan magang baru cocok"
        ).items():
            (ok if status == "ok" else warn)(f"notifikasi {channel}: {status}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        err("uvicorn belum terpasang. Jalankan: pip install -r requirements.txt")
        return 1
    from .web import create_app

    profile_path = default_profile_path(getattr(args, "profile", None))
    os.environ["MAGANGKU_PROFILE"] = str(profile_path)
    os.environ["MAGANGKU_DB"] = str(getattr(args, "db", None) or DEFAULT_DB)
    os.environ["MAGANGKU_SOURCE"] = args.source

    host = args.host
    if host not in ("127.0.0.1", "localhost", "::1") and not args.allow_lan:
        err(f"Menolak mengikat ke {host}.")
        say("  Dashboard menampilkan data pribadi Anda (nama, email, telepon, CV)\n"
            "  TANPA login. Mengikatnya ke alamat non-lokal membuat siapa pun di\n"
            "  jaringan yang sama bisa membacanya.\n", "dim")
        say("  Kalau memang disengaja (mis. akses dari HP di Wi-Fi yang sama):", "dim")
        say(f"    magangku serve --host {host} --allow-lan\n", "bold")
        return 1

    say(f"\nDashboard MagangKu -> http://{host}:{args.port}\n", "bold cyan")
    if host not in ("127.0.0.1", "localhost", "::1"):
        say("  PERINGATAN: terbuka untuk seluruh jaringan lokal, tanpa login.\n", "yellow")
    uvicorn.run(create_app(), host=host, port=args.port, log_level="warning")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    """Test every known Kemnaker endpoint from THIS machine and report reality.

    The sandbox this tool was built in cannot reach kemnaker.go.id, so several
    endpoints are educated guesses. Running this on a normal connection turns
    those guesses into facts - and tells you exactly which ones still work.
    """
    from .endpoints import ALL_ENDPOINTS, CONFIDENCE_LABEL, by_kind
    from .session import Session, SessionClient

    session = Session.load()
    client = SessionClient(session, timeout=args.timeout)

    if session.is_empty:
        say("Tidak ada sesi tersimpan - endpoint publik saja yang bisa diuji.\n"
            "Untuk menguji endpoint privat: `magangku session help`.\n", "yellow")
    else:
        say(f"Memakai sesi tersimpan ({session.summary()['source']}).\n", "dim")

    groups = ["vacancies", "applications", "profile", "reference"]
    if args.kind:
        groups = [args.kind]

    alive: list[str] = []
    rows_out: list[dict[str, Any]] = []

    for kind in groups:
        endpoints = [e for e in by_kind(kind)
                     if not (e.auth == "required" and session.is_empty and args.public_only)]
        if not endpoints:
            continue
        say(f"\n=== {kind.upper()} ===", "bold")
        for endpoint in endpoints:
            if "{vacancy_id}" in endpoint.url:
                say(f"  ~  {endpoint.url}\n     (butuh id lowongan - dilewati)", "dim")
                continue
            url, params = endpoint.build()
            result = client.probe(url, params)
            result["key"] = endpoint.key
            result["confidence"] = endpoint.confidence
            rows_out.append(result)

            if result["ok"]:
                detail = f"{result['items']} item"
                if result["total"]:
                    detail += f", total {result['total']}"
                if result["note"]:
                    detail += f" | {result['note']}"
                say(f"  OK  [{result['status']}] {url}\n      {detail}", "green")
                alive.append(url)
            else:
                label = CONFIDENCE_LABEL.get(endpoint.confidence, endpoint.confidence)
                reason = result["note"] or f"HTTP {result['status']}"
                say(f"  --  [{result['status'] or '---'}] {url}\n"
                    f"      {reason}  ({label})", "dim")

    say("\n" + "-" * 66)
    if alive:
        say(f"{len(alive)} endpoint hidup:", "bold green")
        for url in alive:
            say(f"  * {url}")
        say("\nPakai yang berisi lowongan sebagai sumber:", "dim")
        say(f"  export MAGANGKU_BASE_URL=\"<base-url-nya>\"")
    else:
        say("Tidak ada endpoint yang merespons.", "bold yellow")
        say("Kemungkinan: (a) Cloudflare memblokir jaringan Anda, "
            "(b) semua butuh login - isi sesi lewat `magangku session help`, atau\n"
            "(c) Kemnaker mengubah lagi API-nya.\n"
            "MagangKu tetap jalan penuh dengan `--source fixtures`.", "dim")

    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")
        say(f"\nHasil lengkap -> {path}", "cyan")
    return 0


def cmd_session(args: argparse.Namespace) -> int:
    """Inspect / capture the local Kemnaker session. Never prints raw tokens."""
    if args.action == "help":
        say(HELP_TEXT)
        return 0

    if args.action == "capture":
        from .session import capture_via_browser

        try:
            session = capture_via_browser()
        except RuntimeError as exc:
            err(str(exc))
            return 1
        if session.is_empty:
            err("Tidak ada cookie yang terbaca. Pastikan Anda benar-benar login.")
            return 1
        path = session.save()
        ok(f"Sesi tersimpan di {path.name} (permission 0600, sudah di .gitignore)")
        say(f"   {session.summary()['cookie_count']} cookie, "
            f"token: {'ada' if session.summary()['has_access_token'] else 'tidak ada'}")
        return 0

    # status
    session = Session.load()
    say("\n=== Status Sesi MagangHub ===\n", "bold cyan")
    if session.is_empty:
        warn("Belum ada sesi tersimpan.")
        say("\nItu wajar - MagangKu tetap berfungsi penuh tanpa login "
            "(scrape lowongan bersifat publik).")
        say("Sesi hanya dibutuhkan untuk menarik profil pribadi Anda.")
        say("\nJalankan `magangku session help` untuk cara mengisinya dengan aman.")
        return 0

    info = session.summary()
    ok(f"Sumber        : {info['source']}")
    say(f"Jumlah cookie : {info['cookie_count']}")
    say(f"Nama cookie   : {', '.join(info['cookie_names']) or '-'}")
    say(f"Access token  : {info['token_preview'] or '(tidak ditemukan)'}")
    say("\n(Nilai token sengaja tidak ditampilkan penuh.)", "dim")

    if args.check:
        say("\nMenguji endpoint profil...")
        _, url, log = SessionClient(session).discover_profile()
        for line in log:
            say(f"   {redact(line)}", "dim")
        if url:
            ok(f"Endpoint yang berhasil: {url}")
        else:
            warn("Tidak ada endpoint profil yang merespons.")
            say("Gunakan cara ekspor manual: `magangku sync --from-file profil.json`")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Import the user's real Kemnaker profile into profile.yml."""
    payload: Any = None
    origin = ""

    if args.from_file:
        path = Path(args.from_file)
        if not path.exists():
            err(f"Berkas tidak ditemukan: {path}")
            return 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            err(f"JSON tidak valid: {exc}")
            say("Pastikan Anda menyalin seluruh isi respons (mulai dari '{' ).")
            return 1
        origin = str(path)
    else:
        session = Session.load()
        if session.is_empty:
            err("Belum ada sesi tersimpan.")
            say("\nDua pilihan:")
            say("  1. Ekspor JSON profil dari DevTools, lalu:")
            say("     magangku sync --from-file profil.json     [paling aman]")
            say("  2. Isi MAGANGHUB_COOKIE di .env, lalu ulangi `magangku sync --auto`")
            say("\nDetail: magangku session help")
            return 1

        endpoints = (args.endpoint,) if args.endpoint else PROFILE_ENDPOINTS
        say("Mencari endpoint profil...")
        payload, origin, log = SessionClient(session).discover_profile(endpoints)
        for line in log:
            say(f"   {redact(line)}", "dim")
        if payload is None:
            err("Tidak ada endpoint profil yang bisa diakses.")
            say("\nKemungkinan penyebab: sesi kedaluwarsa, Cloudflare memblokir, "
                "atau endpoint berubah.")
            say("Jalur yang selalu berhasil: `magangku sync --from-file profil.json`")
            say("Caranya: magangku session help")
            return 2

    mapped = map_kemnaker_profile(payload)
    found = mapped["_found"]

    say("\n=== Data yang terbaca ===", "bold cyan")
    say(f"Identitas : {', '.join(found['identity_fields']) or '(tidak ada)'}")
    say(f"Jurusan   : {found['majors']}")
    say(f"Keahlian  : {found['skills']}")
    say(f"Provinsi  : {found['province'] or '-'}")

    if not any([found["identity_fields"], found["majors"], found["skills"]]):
        warn("\nTidak ada field yang dikenali dari payload ini.")
        say("Kemungkinan Anda menyalin respons yang salah (bukan data profil).")
        say("Cari permintaan yang isinya memuat nama & riwayat pendidikan Anda.")
        if args.dump:
            say("\nStruktur payload (untuk diagnosis):")
            say(json.dumps(payload, ensure_ascii=False, indent=1)[:1500], "dim")
        else:
            say("\nTambahkan --dump untuk melihat struktur payload-nya.")
        return 1

    target = ROOT / "profile.yml"
    base = load_profile_dict(target) or load_profile_dict(ROOT / "profile.example.yml")
    updated, changes = apply_to_profile(base, mapped, overwrite=args.overwrite)

    if not changes:
        ok("\nProfil Anda sudah selaras - tidak ada yang perlu diubah.")
        return 0

    say("\n=== Perubahan ===", "bold cyan")
    for change in changes:
        say(f"   {change}")

    if args.dry_run:
        say("\n(--dry-run: tidak ada yang ditulis)", "yellow")
        return 0

    if target.exists():
        backup = target.with_suffix(".yml.bak")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        say(f"\nCadangan disimpan: {backup.name}", "dim")

    write_profile_dict(target, updated)
    ok(f"profile.yml diperbarui dari {origin}")
    say("\nLangkah berikutnya: magangku match --top 20")
    return 0


def cmd_provinces(args: argparse.Namespace) -> int:
    provinces = load_provinces()
    if not provinces:
        warn("Daftar provinsi tidak tersedia.")
        return 1
    say("\nKode provinsi (untuk --province):\n", "bold cyan")
    for i in range(0, len(provinces), 2):
        row = provinces[i:i + 2]
        say("   ".join(f"{p['kode']:>3}  {p['nama']:<32}" for p in row))
    return 0


# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magangku",
        description="MagangKu - pencari & pencocok lowongan magang MagangHub Kemnaker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""contoh:
  magangku doctor
  magangku profile init --cv cv.txt
  magangku scrape --source fixtures
  magangku match --top 20 --explain 3 --export
  magangku apply --top 5
  magangku watch --source fixtures --channel console
  magangku serve
""",
    )
    parser.add_argument("--profile", help="path profile.yml")
    parser.add_argument("--db", help="path database SQLite")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_source(p: argparse.ArgumentParser, default: str = "db") -> None:
        p.add_argument("--source", choices=["db", "fixtures", "live", "dir"],
                       default=default, help=f"sumber data (default: {default})")
        p.add_argument("--data-dir", default=str(RAW_DIR),
                       help="direktori JSON bila --source dir")

    p = sub.add_parser("doctor", help="cek kesiapan sistem")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("profile", help="kelola profil pelamar")
    p.add_argument("action", choices=["init", "show", "from-cv"], nargs="?", default="show")
    p.add_argument("--cv", help="path CV (.txt/.md)")
    p.add_argument("--force", action="store_true", help="timpa profile.yml yang ada")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("scrape", help="ambil & simpan data lowongan")
    p.add_argument("--source", choices=["live", "fixtures", "dir"], default="live")
    p.add_argument("--data-dir", default=str(RAW_DIR))
    p.add_argument("--province", help="kode provinsi, mis. 34 (DIY)")
    p.add_argument("--limit", type=int, default=100, help="item per halaman")
    p.add_argument("--max-pages", type=int, default=None, help="batas jumlah halaman")
    p.add_argument("--delay", type=float, default=1.0, help="jeda antar request (detik)")
    p.add_argument("--save-raw", action="store_true", help="simpan JSON mentah")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_scrape)

    p = sub.add_parser("match", help="nilai & urutkan lowongan sesuai profil")
    add_source(p)
    p.add_argument("--top", type=int, default=20, help="jumlah hasil (0 = semua)")
    p.add_argument("--min-score", type=float, default=0.0)
    p.add_argument("--include-blocked", action="store_true",
                   help="tampilkan juga yang kena filter keras")
    p.add_argument("--explain", type=int, default=0, metavar="N",
                   help="tampilkan rincian skor N teratas")
    p.add_argument("--export", action="store_true", help="ekspor CSV/JSON/MD/HTML")
    p.add_argument("--out", help="folder output")
    p.add_argument("--open", action="store_true", help="buka laporan HTML")
    p.set_defaults(func=cmd_match)

    p = sub.add_parser("apply", help="siapkan berkas lamaran (assisted)")
    add_source(p)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--min-score", type=float, default=60.0)
    p.add_argument("--lang", choices=["id", "en"], default=None)
    p.add_argument("--out", help="folder output")
    p.add_argument("--open", action="store_true", help="buka halaman apply pertama")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("track", help="catat status lamaran")
    p.add_argument("vacancy_id")
    p.add_argument("--status", choices=list(VALID_STATUSES), default="applied")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_track)

    p = sub.add_parser("status", help="ringkasan progres lamaran")
    p.add_argument("--filter-status", choices=list(VALID_STATUSES))
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("watch", help="deteksi lowongan baru + notifikasi")
    p.add_argument("--source", choices=["live", "fixtures"], default="live")
    p.add_argument("--province")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--delay", type=float, default=1.0)
    p.add_argument("--min-score", type=float, default=0.0)
    p.add_argument("--channel", action="append",
                   choices=["console", "ntfy", "telegram"])
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("serve", help="jalankan dashboard web")
    p.add_argument("--host", default="127.0.0.1",
                   help="default hanya localhost; data pribadi tidak diekspos ke jaringan")
    p.add_argument("--allow-lan", action="store_true",
                   help="izinkan akses dari jaringan lokal (sadar risiko: tanpa login)")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--source", choices=["db", "fixtures"], default="db")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("session", help="kelola sesi login MagangHub (lokal)")
    p.add_argument("action", choices=["status", "help", "capture"], nargs="?",
                   default="status")
    p.add_argument("--check", action="store_true",
                   help="uji endpoint profil dengan sesi saat ini")
    p.set_defaults(func=cmd_session)

    p = sub.add_parser("sync", help="tarik profil resmi Anda dari MagangHub")
    p.add_argument("--from-file", metavar="FILE",
                   help="JSON profil hasil ekspor DevTools (cara paling aman)")
    p.add_argument("--auto", action="store_true",
                   help="coba ambil otomatis memakai sesi tersimpan")
    p.add_argument("--endpoint", help="paksa satu URL endpoint tertentu")
    p.add_argument("--overwrite", action="store_true",
                   help="timpa nilai yang sudah Anda isi sendiri")
    p.add_argument("--dry-run", action="store_true", help="tampilkan perubahan saja")
    p.add_argument("--dump", action="store_true",
                   help="tampilkan struktur payload untuk diagnosis")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("probe", help="uji semua endpoint Kemnaker dari mesin Anda")
    p.add_argument("--kind", choices=["vacancies", "applications", "profile", "reference"],
                   help="uji satu kategori saja")
    p.add_argument("--public-only", action="store_true",
                   help="lewati endpoint yang butuh login")
    p.add_argument("--timeout", type=float, default=15.0, help="detik per endpoint")
    p.add_argument("--json", help="simpan hasil lengkap ke berkas JSON")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("provinces", help="daftar kode provinsi")
    p.set_defaults(func=cmd_provinces)

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        say("\nDibatalkan.", "yellow")
        return 130
    except FileNotFoundError as exc:
        err(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
