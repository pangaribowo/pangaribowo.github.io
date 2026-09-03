# pangaribowo.github.io — Portofolio v2

![Vite](https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Three.js](https://img.shields.io/badge/Three.js-r180-000000?logo=threedotjs&logoColor=white)
![GitHub Pages](https://img.shields.io/badge/Deploy-GitHub%20Pages-222?logo=github)

Portofolio SPA **Fatahillah Alif Pangaribowo** — Object Detection Research Assistant di ITDA Yogyakarta, inventor HKI *Skrining Kanker Payudara*, Distinction Graduate Bangkit Academy (Cloud Computing).

🌐 **Live:** https://pangaribowo.github.io

## Fitur

- 🪟 **Glassmorphism** di seluruh komponen — blur + saturate, border tipis, highlight inset, spotlight pointer
- 🌗 **Dual theme** (dark/light) anti-FOUC, persisten, hormati `prefers-color-scheme`
- 🌌 **Three.js GalaxyScene** — 6.500 partikel galaksi spiral + starfog, parallax pointer, hemat baterai (pause saat tab tersembunyi)
- ✨ **Animasi kelas atas** — Framer Motion stagger, kartu 3D-tilt, tombol magnetic, reveal-on-scroll, CountUp, mesin ketik peran, cursor aura, progress bar scroll
- 🌍 **Bilingual ID/EN** — bawaan Indonesia, toggle tersimpan
- 🔎 **SEO penuh** — Open Graph, Twitter Card, JSON-LD Person, robots.txt, favicon SVG
- 🧱 **Konten sumber-tunggal** — seluruh riwayat dan data proyek terpusat di `src/data/portfolio.ts`
- ⚡ **High-Performance Architecture** — modular component layout dengan strict TypeScript type safety

## Stack

| Lapisan | Pilihan | Alasan |
|---|---|---|
| Bundler | **Vite 7** | dev cepat, chunk manual (`three`, `vendor`) |
| UI | **React 19 + TypeScript strict** | SPA komponen, keselamatan tipe penuh |
| 3D | **three.js** (tanpa wrapper) | kontrol render loop & memori langsung |
| Animasi | **framer-motion** | spring fisika, layout animation |
| Ikon | **lucide-react** | konsisten, tree-shakeable |
| CSS | custom tokens (tanpa framework) | glassmorphism presisi di dua tema |

## Menjalankan

```bash
npm install        # sekali
npm run dev        # dev server
npm run typecheck  # gerbang mutu: TS strict
npm run build      # produksi → dist/
npm run preview    # pratinjau hasil build
```

## Struktur

```
├── .github/workflows/deploy.yml  # CI → GitHub Pages
├── public/                       # favicon.svg, robots.txt, og.jpg
├── src/
│   ├── data/portfolio.ts         # Sumber kebenaran konten profil & proyek
│   ├── i18n/copy.ts              # kamus ID/EN
│   ├── styles/global.css         # token tema + primitif glass
│   ├── context.tsx               # tema & bahasa global
│   ├── components/
│   │   ├── GalaxyScene.tsx       # latar three.js
│   │   ├── ui.tsx                # Reveal, Magnetic, TiltCard, CountUp, TypedRoles…
│   │   ├── Navbar.tsx            # nav glass + progress scroll + rail samping + responsive hamburger
│   │   ├── Hero.tsx / About.tsx / Journey.tsx / Projects.tsx / Contact.tsx
│   └── App.tsx / main.tsx
```

## Deploy

Push ke `main` memicu **GitHub Actions** (typecheck → build → publish). Syarat satu kali: **Settings → Pages → Source: GitHub Actions**.

---

© 2026 Fatahillah Alif Pangaribowo · Yogyakarta, Indonesia
