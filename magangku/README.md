# MagangKu

**Sistem end-to-end untuk mencari, menilai, dan menyiapkan lamaran magang di [MagangHub Kemnaker](https://maganghub.kemnaker.go.id).**

Masalahnya bukan kurangnya lowongan — MagangHub punya ribuan. Masalahnya
menemukan **yang cocok dengan profil Anda**, sebelum kuotanya habis.
MagangKu mengambil data lowongan, menilainya terhadap profil Anda dengan skor
yang bisa dijelaskan, lalu menyiapkan surat lamaran + checklist siap kirim.

```
scrape ──▶ normalize ──▶ store (SQLite) ──▶ match (skor 0-100) ──▶ surat + checklist ──▶ Anda kirim
                              │                     │
                          riwayat &            dashboard web
                       deteksi lowongan baru    / CSV / HTML
```

---

## Prinsip: assisted, bukan auto-submit

MagangKu **tidak** mengirim lamaran atas nama Anda dan **tidak pernah** meminta
password MagangHub. Sistem ini menyiapkan semua bahan — surat, checklist, link
langsung — lalu Anda yang menekan tombol kirim.

Alasannya bukan sekadar teknis:

- **Sesuai aturan main.** Auto-submit massal berisiko melanggar ketentuan
  layanan dan bisa berakibat akun Anda diblokir.
- **Kualitas menang atas kuantitas.** Pemberi kerja menyaring pelamar; 5 lamaran
  yang dipersonalisasi mengalahkan 50 lamaran serabutan.
- **Anda tetap memegang kendali.** Tidak ada kejutan lamaran terkirim ke posisi
  yang ternyata tidak Anda inginkan.

---

## Instalasi

Butuh **Python 3.10+**.

```bash
cd magangku
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m magangku.cli doctor      # cek semuanya beres
```

`doctor` memeriksa dependensi, profil, data contoh, database, dan koneksi ke
MagangHub — lalu memberi tahu persis apa yang perlu diperbaiki.

---

## Mulai cepat (5 menit)

```bash
# 1. Buat profil — otomatis diisi dari CV Anda bila ada
python -m magangku.cli profile init --cv cv.txt
#    (belum punya cv.txt? cukup: profile init, lalu edit profile.yml manual)

# 2. Ambil data lowongan
python -m magangku.cli scrape                      # dari server Kemnaker
python -m magangku.cli scrape --source fixtures    # atau data contoh (offline)

# 3. Lihat yang paling cocok
python -m magangku.cli match --top 20 --explain 3

# 4. Siapkan berkas lamaran untuk 5 teratas
python -m magangku.cli apply --top 5

# 5. Buka dashboard visual
python -m magangku.cli serve                       # http://localhost:8000
```

---

## Cara kerja penilaian

Setiap lowongan dinilai **0–100** dari enam komponen berbobot. Tidak ada AI,
tidak ada kotak hitam — setiap angka bisa ditelusuri asalnya.

| Komponen      | Bobot | Yang dinilai |
|---------------|------:|--------------|
| `major`       |  30 % | Kecocokan program studi (paham sinonim: *Informatika* ≈ *Ilmu Komputer*) |
| `skills`      |  22 % | Skill Anda yang benar-benar disebut di deskripsi lowongan |
| `location`    |  18 % | Kota prioritas > provinsi > luar preferensi (paham area metro) |
| `opportunity` |  15 % | Peluang diterima: kuota vs jumlah pendaftar |
| `level`       |  10 % | Kecocokan jenjang pendidikan |
| `urgency`     |   5 % | Sisa waktu pendaftaran |

Semua bobot bisa diubah di `profile.yml`. Jalankan `--explain N` untuk melihat
rinciannya:

```
1. Fullstack Developer - Ruang Media Solusi  [91.8/100]
   major         1.00 x0.30  =  30.0  ############ Jurusan cocok persis: Informatika
   skills        1.00 x0.22  =  22.0  ############ skill cocok: python, javascript, sql, git
   location      1.00 x0.18  =  18.0  ############ Kota prioritas: Kota Yogyakarta
   level         1.00 x0.10  =  10.0  ############ Jenjang sesuai: Diploma, Sarjana
   opportunity   0.65 x0.15  =   9.8  #######      15 pelamar / 3 kuota (5.0:1, est. 19%)
   urgency       0.40 x0.05  =   2.0  ####         Masih lama (25 hari)
```

**Filter keras** (di `profile.yml` → `filters`) membuang lowongan sebelum
dinilai: pendaftaran tutup, kuota terlalu kecil, persaingan terlalu ketat, kata
kunci terlarang, di luar provinsi tertentu. Kalau hasilnya kosong, MagangKu
memberi tahu penyebab terbanyaknya, bukan sekadar "tidak ada hasil".

---

## Perintah

| Perintah | Fungsi |
|----------|--------|
| `doctor` | Cek kesiapan sistem & diagnosis masalah |
| `profile init \| show \| from-cv` | Kelola profil pelamar |
| `scrape` | Ambil & simpan lowongan (`--source live\|fixtures\|dir`) |
| `match` | Nilai & urutkan (`--top`, `--explain`, `--export`, `--min-score`) |
| `apply` | Siapkan surat + checklist (assisted) |
| `track <id> --status applied` | Catat progres lamaran |
| `status` | Ringkasan semua lamaran Anda |
| `watch` | Deteksi lowongan **baru** lalu kirim notifikasi |
| `serve` | Dashboard web |
| `provinces` | Daftar kode provinsi untuk `--province` |

Selalu ada `--help` di setiap subperintah.

---

## Profil Anda

Semua perilaku dikendalikan `profile.yml` (disalin dari `profile.example.yml`,
dan sudah masuk `.gitignore` karena berisi data pribadi).

```yaml
identity:
  name: "Bowo Pangaribowo"
  level: "Sarjana"
majors: ["Teknik Informatika"]
skills: [python, javascript, sql, react]
location:
  cities: ["Yogyakarta", "Sleman"]
  allow_outside: true      # false = buang total lowongan di luar preferensi
filters:
  only_open: true
  max_competition: 0       # mis. 10 = buang yang >10 pelamar per slot
weights:
  major: 0.30              # naikkan yang paling Anda pedulikan
  opportunity: 0.15
```

### Mengisi dari CV

```bash
python -m magangku.cli profile from-cv --cv cv.txt
```

Mendeteksi nama, email, telepon, kampus, jenjang, IPK, jurusan, dan ±100 skill.
Hasilnya **tebakan** — selalu periksa ulang. Untuk PDF, konversi dulu:

```bash
pdftotext -layout cv.pdf cv.txt
```

Nilai yang sudah Anda tulis sendiri **tidak akan ditimpa**.

---

## Dashboard web

```bash
python -m magangku.cli serve            # http://localhost:8000
```

Kartu lowongan terurut skor, filter langsung (teks, skor minimum, kategori,
provinsi, pemerintah/swasta), dan panel detail berisi rincian skor, deskripsi
lengkap, **surat lamaran siap salin**, serta checklist pra-kirim. Tombol
*Simpan* / *Tandai sudah dilamar* menyimpan status ke database.

Tanpa build step, tanpa CDN — HTML/CSS/JS menyatu dalam satu file dan jalan
sepenuhnya offline.

---

## Pemantauan otomatis

`watch` membandingkan hasil scrape dengan database, jadi ia tahu mana yang
**benar-benar baru**, lalu mengirim notifikasi bila skornya melewati ambang.

```bash
python -m magangku.cli watch --min-score 75 --channel ntfy
```

Kanal: `console`, `ntfy` (tanpa akun — pilih nama topik di `.env`, pasang
aplikasi ntfy di HP), `telegram` (bot token + chat id).

Contoh cron tiap 6 jam:

```cron
0 */6 * * * cd /path/ke/magangku && .venv/bin/python -m magangku.cli watch --min-score 75 --channel ntfy
```

---

## Sumber data & mode offline

Data diambil dari API publik yang dipakai situs MagangHub sendiri:

```
GET https://maganghub.kemnaker.go.id/be/v1/api/list/vacancies-aktif
    ?order_by=jumlah_kuota&order_direction=DESC&page=1&limit=100[&kode_provinsi=34]
```

Scraper-nya sopan: ada jeda antar-permintaan (`MAGANGKU_DELAY`), retry dengan
backoff eksponensial, dan berhenti sendiri di halaman terakhir.

> **Catatan penting.** MagangHub berada di belakang Cloudflare dan kerap
> memblokir IP datacenter, VPN, CI runner, dan sandbox. Bila `scrape` gagal
> koneksi, itu **bukan bug** — jalankan dari koneksi rumah/kantor biasa.
>
> Agar seluruh sistem tetap bisa dicoba tanpa jaringan, tersedia
> **120 lowongan contoh nyata** (Yogyakarta + Jawa Tengah) di `data/fixtures/`:
>
> ```bash
> python -m magangku.cli scrape --source fixtures
> ```
>
> Isi lowongan asli; hanya **tanggal jadwalnya digeser** agar tetap relevan
> sebagai demo.

---

## Struktur proyek

```
magangku/
├── magangku/
│   ├── models.py      # Vacancy: bentuk data bersih + metrik turunan
│   ├── normalize.py   # payload API berantakan  ->  Vacancy
│   ├── profile.py     # profil + kamus jurusan/jenjang/kota Indonesia
│   ├── matcher.py     # mesin skor yang bisa dijelaskan
│   ├── scraper.py     # klien API + pemuat data offline
│   ├── storage.py     # SQLite: riwayat, deteksi baru, tracker lamaran
│   ├── cv.py          # CV teks -> profil
│   ├── letter.py      # surat lamaran + checklist
│   ├── report.py      # ekspor CSV / JSON / Markdown / HTML
│   ├── notify.py      # console / ntfy / Telegram
│   ├── web.py         # dashboard FastAPI
│   └── cli.py         # antarmuka baris perintah
├── data/fixtures/     # 120 lowongan contoh (offline)
├── tests/             # 45 tes
└── profile.example.yml
```

---

## Tes

```bash
python -m pytest tests/ -q      # 45 passed
```

Mencakup normalisasi data rusak (null, HTML, JSON bersarang), logika skor &
filter keras, deteksi perubahan di SQLite, parsing CV, dan escaping HTML pada
laporan.

---

## Privasi & keamanan

- Semua pemrosesan **lokal**. Tidak ada data yang dikirim ke pihak ketiga.
- `profile.yml`, `cv.txt`, `.env`, dan `*.db` sudah ada di `.gitignore`.
- Sistem **tidak pernah** meminta password MagangHub.
- `MAGANGHUB_COOKIE` di `.env` bersifat opsional dan hanya dipakai lokal.

---

## Diadaptasi dari riset komunitas

Dibangun setelah menelaah repositori peserta MagangHub batch sebelumnya —
mengambil ide yang berhasil dan memperbaiki yang rapuh:

| Sumber | Yang diambil | Yang diperbaiki di sini |
|--------|--------------|--------------------------|
| [ridwaanhall/maganghub-filters](https://github.com/ridwaanhall/maganghub-filters) | Endpoint `vacancies-aktif`, ide estimasi peluang diterima | Dijadikan model data bertipe + normalisasi tahan-null |
| [nandasafiqalfiansyah/maganghub-api](https://github.com/nandasafiqalfiansyah/maganghub-api) | Konfirmasi base URL `/be/v1/api/list` | Klien Python dengan retry/backoff, bukan layanan terpisah |
| [sehade/maganghub-ai-filter](https://github.com/sehade/maganghub-ai-filter) | Gagasan pencocokan CV ↔ lowongan | Skor deterministik & bisa dijelaskan — tanpa Playwright, tanpa scraping UI ChatGPT yang mudah rusak |
| [Tamatimtam/maganghub-notifier](https://github.com/Tamatimtam/maganghub-notifier) | Pola notifikasi ntfy | Diperluas ke Telegram + deteksi "baru" berbasis database, bukan regex HTML |
| [Tamatimtam/maganghub-explorer](https://github.com/Tamatimtam/maganghub-explorer) | Pengelompokan wilayah & tier | Menjadi kamus alias kota/metro di mesin lokasi |
| [faprikaa/maganghub-autopresence](https://github.com/faprikaa/maganghub-autopresence) | Pola autentikasi berbasis cookie | Sengaja **tidak** dipakai untuk auto-submit — hanya assisted |

Perbedaan utama: proyek-proyek itu memecahkan satu bagian (scrape *atau* filter
*atau* notifikasi). MagangKu menyatukannya menjadi satu alur utuh dengan
persistensi, penjelasan skor, pembuatan surat, dan pelacakan lamaran.

---

## Lisensi & etika

Untuk penggunaan pribadi. Hormati ketentuan layanan MagangHub: pakai jeda
permintaan yang wajar, jangan bombardir server, dan jangan gunakan untuk spam
lamaran massal. Data lowongan milik Kemnaker RI dan masing-masing pemberi kerja.
