# Audit Arsitektur MagangKu

Dokumen ini menjawab dua pertanyaan Anda:

1. Semuanya masih Python — bagaimana supaya dashboard-nya modern?
2. Keputusan infra/arsitektur mana yang perlu diaudit dan di-upgrade?

Semua angka di bawah **hasil ukur**, bukan perkiraan. Tanggal audit: 7 Sep 2026,
pada commit `4ce1b87` (sebelum perbaikan), 5.699 baris Python.

---

## Ringkasan eksekutif

Dua temuan **sudah saya perbaiki langsung** karena berisiko nyata, bukan sekadar
soal selera arsitektur:

| # | Temuan | Bukti | Status |
|---|---|---|---|
| 1 | Dashboard membocorkan data pribadi ke seluruh jaringan | `GET /api/profile/raw` dari IP non-localhost mengembalikan nama, email, telepon, isi CV. Tidak ada satu pun route terautentikasi. | **Diperbaiki** (`a3d7102`) |
| 2 | Tidak ada versioning skema DB | `PRAGMA user_version` = 0. Menambah kolom di rilis berikutnya = `no such column` di DB pengguna lama. | **Diperbaiki** (`a3d7102`) |

Sisanya rekomendasi berprioritas, tidak saya kerjakan tanpa persetujuan Anda.

---

## Bagian 1 — Soal "masih Python", dashboard modern

### Klarifikasi dulu: Python bukan penyebabnya

Dashboard sekarang **sudah** berbasis web (HTML/CSS/JS di browser). Python hanya
jalan di server sebagai penyedia JSON. Jadi masalahnya bukan "masih Python".

Saya ukur dulu sebelum menyimpulkan:

```
GET /                     200    14.1 ms   32.2 KB
GET /api/bootstrap        200    10.0 ms    2.1 KB
GET /api/matches?top=50   200    73.7 ms  270.4 KB
GET /api/stats            200    13.0 ms    0.2 KB
```

**Performa bukan masalah.** 74 ms untuk 50 lowongan dengan skoring penuh itu
cepat. Kalau saya ganti ke React/Next.js sekarang, angka-angka ini tidak akan
membaik — malah kemungkinan lebih lambat karena ada bundle JS yang harus diunduh.

### Yang benar-benar bermasalah

Masalahnya **bukan** performa, melainkan **cara frontend ditulis**:

| Ukuran | Nilai | Kenapa jadi masalah |
|---|---|---|
| `web.py` | 1.087 baris | Satu berkas memuat backend + frontend |
| Blob `PAGE` | 32.925 karakter / 611 baris | HTML+CSS+JS sebagai *string Python* |
| — CSS | 6.069 karakter | Tanpa highlighting, tanpa linting, tanpa autocomplete |
| — JS | 15.715 karakter / 293 baris | Sama; salah ketik baru ketahuan saat runtime di browser |
| `innerHTML =` | 20 tempat | Tiap satu = potensi XSS kalau lupa `esc()` |
| `esc()` dipanggil | 48 kali | Rasionya bagus, tapi dijaga manual — sekali lupa, bocor |

Inilah biaya sebenarnya: **tidak ada jaring pengaman**. Tidak ada type checking,
tidak ada linter, tidak ada component test. Selama fitur masih sedikit ini
tertahankan; begitu bertambah, tiap perubahan jadi taruhan.

### Tiga pilihan, dengan konsekuensi jujur

**Opsi A — Rapikan yang ada (½ hari)**
Keluarkan CSS/JS ke `static/`, pakai Jinja2 untuk template. Bonus: escaping jadi
otomatis, 20 titik XSS itu hilang sebagai kelas masalah.
→ Tampilan **tidak berubah**. Yang berubah: bisa di-lint, bisa diedit dengan
   nyaman.

**Opsi B — Alpine.js + Tailwind via CDN (1–2 hari)**
Tetap satu server Python, tanpa build step, tanpa `node_modules`. Dapat
reactivity deklaratif dan komponen visual modern.
→ Rasio manfaat/biaya **terbaik** untuk kasus Anda. Tetap gampang dijalankan
   klien awam: `magangku serve`, selesai.

**Opsi C — Next.js/React terpisah (1–2 minggu)**
Frontend modern penuh: component library, dark mode, animasi, state management.
→ **Saya tidak menyarankan ini sekarang.** Konsekuensinya bertabrakan langsung
   dengan batasan Anda sendiri: klien awam harus menginstal Node.js, menjalankan
   dua proses (API + frontend), dan `scripts/init_private_repo.sh` jadi jauh
   lebih rumit. Anda menukar kemudahan pakai — persyaratan utama Anda — demi
   kosmetik.

**Rekomendasi: A sekarang, B kalau Anda mau tampilan yang benar-benar terasa
modern.** C hanya masuk akal kalau nanti ada banyak pengguna sekaligus.

---

## Bagian 2 — Audit infra & arsitektur

### 2.1 Yang sudah benar (pertahankan)

| Keputusan | Kenapa tepat |
|---|---|
| SQLite, bukan Postgres | Aplikasi single-user lokal. Tanpa server, tanpa Docker, file tunggal gampang di-backup. |
| Fixture offline 120 lowongan | Sistem tetap 100% bisa dicoba walau Cloudflare memblokir. Ini yang menyelamatkan proyek saat API berubah. |
| Skoring deterministik lokal, bukan LLM | Bisa dijelaskan (`--explain`), gratis, reproducible, jalan offline. Repo `sehade` menempuh jalur drive-UI-ChatGPT; rapuh dan lambat. |
| Allowlist domain + redaksi token | Token tak mungkin bocor ke log/error, request tak mungkin nyasar ke domain lain. |
| Assisted, bukan auto-submit | Sesuai batasan Anda; juga menghindari pelanggaran ToS. |
| Registri endpoint berlabel kejujuran | Saat API Kemnaker berubah lagi, yang perlu disunting satu berkas, bukan berburu di seluruh kode. |

### 2.2 Temuan yang sudah diperbaiki

**Temuan 1 — Data pribadi terekspos ke jaringan (SERIUS)**

Bukti nyata, bukan teoretis:

```
$ curl http://<ip-lan>:8000/api/profile/raw
{"path":".../profile.yml","yaml":"identity:\n  name: Bowo Pangaribowo\n
  email: bowo.pangaribowo@gmail.com\n  phone: 081234567890\n ..."}
```

Penyebab: `--host` default `0.0.0.0` sementara nol route punya autentikasi.
Di Wi-Fi kafe atau kos, siapa pun sejaringan bisa membaca CV dan kontak Anda.

Perbaikan: default `127.0.0.1`. Untuk mengikat ke alamat lain wajib
`--allow-lan` eksplisit, disertai peringatan. Dua tes mengunci perilaku ini.

**Temuan 2 — Tidak ada migrasi skema**

`PRAGMA user_version` bernilai 0. `CREATE TABLE IF NOT EXISTS` aman untuk tabel
baru, tapi tidak bisa menambah kolom ke tabel yang sudah ada di mesin pengguna.
Terverifikasi gagal: `no such column`.

Perbaikan: `SCHEMA_VERSION` + peta `MIGRATIONS`, dijalankan saat `Store` dibuka.
DB lama tanpa cap versi ikut ter-migrasi. Diuji pada DB baru maupun DB legacy.

### 2.3 Rekomendasi berprioritas (belum dikerjakan)

**P1 — CI tidak menjalankan tes.** `.github/workflows/watch.yml` hanya cron
pemantau. 93 tes yang kita punya tidak pernah jalan otomatis; regresi baru
ketahuan saat dipakai. *Perbaikan: satu workflow `test.yml`, ~15 menit.*

**P2 — Operasi jaringan memblokir event loop.** Semua route `def` biasa (22
route, 0 `async def`). FastAPI melemparkannya ke threadpool sehingga tidak fatal,
tapi `POST /api/refresh` yang men-scrape puluhan halaman membuat UI tampak
menggantung tanpa progres. *Perbaikan: jadikan pekerjaan latar + endpoint status,
atau minimal streaming progres. ~2–3 jam.*

**P3 — Request body tidak bertipe.** Enam route memakai `dict[str, Any] = Body(...)`.
Kiriman salah bentuk baru meledak di dalam fungsi, dan dokumentasi otomatis
FastAPI jadi kosong. *Perbaikan: model Pydantic per endpoint. ~1 jam.*

**P4 — Fitur komunitas yang belum kita punya.** Dari repo yang sudah saya riset:

| Fitur | Sumber | Nilainya untuk Anda |
|---|---|---|
| Enrichment penyelenggara (BUMN, tier, Jabodetabek) | `Tamatimtam/maganghub-explorer` (1.700 penyelenggara) | Bisa jadi sinyal skoring baru: prioritaskan BUMN/perusahaan tier atas |
| Riwayat jumlah pendaftar per waktu | `maganghub-notifier` | Kita simpan `snapshots` tapi belum divisualkan — padahal bisa menunjukkan "sepi peminat, buruan lamar" |
| Filter multi-kriteria tersimpan | `ridwaanhall/maganghub-filters` | Simpan preset pencarian, tak perlu set ulang tiap kali |

Yang **tidak** perlu kita tiru: pendekatan `sehade` (Playwright non-headless
mengemudikan UI ChatGPT) — rapuh, lambat, dan melanggar ToS.

**P5 — Ketergantungan pada satu titik yang bisa hilang.** Endpoint daftar
lowongan di gateway baru belum ditemukan. Mitigasi yang sudah ada (kandidat
berlapis + fixture) sudah tepat; tambahan yang layak: cache respons mentah agar
kalau API mati total, data terakhir tetap bisa dipakai.

---

## Urutan yang saya sarankan

1. ~~Tutup kebocoran data pribadi~~ — **selesai**
2. ~~Versioning skema DB~~ — **selesai**
3. CI menjalankan tes (P1) — 15 menit, langsung terasa
4. Rapikan frontend, Opsi A (P3 sekaligus) — ½ hari
5. Enrichment penyelenggara + grafik riwayat pendaftar (P4) — nilai tambah paling terasa bagi Anda sebagai pencari magang
6. Alpine.js + Tailwind (Opsi B) — hanya kalau Anda memang ingin tampilannya berubah

Poin 5 saya taruh di atas poin 6 dengan sengaja: **menambah sinyal pencocokan
lebih berguna bagi Anda ketimbang mempercantik tampilan.** Tujuan Anda menemukan
magang yang cocok, bukan punya dashboard yang indah.
