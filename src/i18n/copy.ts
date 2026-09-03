/* Kamus UI bilingual — Indonesia (default) & English */
export type Lang = 'id' | 'en';

const copy = {
  id: {
    nav: { about: 'Tentang', skills: 'Keahlian', journey: 'Perjalanan', projects: 'Proyek', contact: 'Kontak' },
    hero: {
      eyebrow: 'Halo, saya',
      lead: 'Asisten riset object detection di ITDA Yogyakarta; inventor HKI skrining kanker payudara berbasis CNN; lulusan Distinction Bangkit Academy (Cloud Computing). Saya membangun aplikasi web dan sesekali menyimulasikan galaksi.',
      cta1: 'Lihat Proyek',
      cta2: 'Hubungi Saya',
      badgeResearch: 'Object Detection',
      badgeResearchSub: 'Computer Vision · ITDA',
      badgeDev: 'Software Developer',
      badgeDevSub: 'React · Three.js · Linux',
      location: 'Yogyakarta, Indonesia',
      open: 'Terbuka untuk kolaborasi',
      scroll: 'Gulir',
    },
    roles: ['Object Detection Researcher', 'Machine Learning Engineer-in-Training', 'Web Developer', 'Linux & Kernel Tinkerer'],
    stats: { repos: 'Repositori Publik', languages: 'Bahasa Pemrograman', hki: 'HKI Terdaftar (Inventor)', since: 'Ngoding Sejak' },
    section: {
      about: { num: '01', eyebrow: 'Tentang saya', title: 'Peneliti deteksi objek yang membangun perangkat lunak dari Yogyakarta.' },
      skills: { num: '02', eyebrow: 'Keahlian', title: 'Perangkat yang saya pakai sehari-hari.' },
      journey: { num: '03', eyebrow: 'Perjalanan', title: 'Riset, industri, organisasi — dirangkum.' },
      projects: { num: '04', eyebrow: 'Proyek', title: 'Hal-hal yang pernah saya bangun.' },
      contact: { num: '05', eyebrow: 'Kontak', title: 'Mari terhubung.' },
    },
    about: {
      p1: 'Saya mahasiswa Informatika di <strong>Institut Teknologi Dirgantara Adisutjipto (ITDA)</strong> Yogyakarta (2022–2026) yang sedang meneliti <strong>object detection</strong>. Sebelumnya saya ikut riset <strong>CNN untuk skrining kanker payudara</strong> — hasilnya terdaftar sebagai HKI dengan saya sebagai salah satu inventor.',
      p2: 'Di luar laboratorium, saya membangun aplikasi web — dari <strong>CodeIgniter 4</strong> sampai <strong>React + Three.js</strong> — dan mengotomatisasi apa pun di Linux (ZRAM, dotfiles, kernel). Saya pegang predikat <strong>Distinction Graduate</strong> jalur Cloud Computing di Bangkit Academy serta sertifikasi profesional Dicoding.',
      p3: 'Komunitas juga bagian dari identitas saya: <strong>IT Executive di Adisutjipto Linux Community</strong> dan aktif di <strong>HMF ITDA</strong>. Ketertarikan lain: penerbangan, luar angkasa, dan teka-teki CTF.',
      terminalTitle: 'alif@itda:~$ whoami',
      education: 'Pendidikan',
      highlights: 'Sorotan',
      honorBangkit: 'Bangkit Academy — Distinction (Cloud Computing, 2024)',
      honorHki: 'Inventor HKI Skrining Kanker Payudara — EC002024260420 (DJKI, 2024)',
      honorDicoding: 'Sertifikasi Profesional Dicoding — Software Development (2024)',
    },
    journey: { work: 'Pengalaman Kerja & Riset', education: 'Pendidikan', badgeResearch: 'Riset', badgeWork: 'Industri', badgeOrg: 'Organisasi', badgeEdu: 'Pendidikan' },
    projects: { featured: 'Unggulan', archive: 'Arsip proyek lainnya', visit: 'Demo Live', source: 'Kode Sumber' },
    contact: {
      title: 'Mari terhubung.',
      desc: 'Tertarik berkolaborasi di riset computer vision, proyek web, atau sekadar ngobrol teknologi? Jangkau saya lewat kanal ini:',
    },
    footer: {
      built: 'Dirancang & dibangun dengan Vite, React, TypeScript, dan Three.js.',
      source: 'Lihat kode sumber',
      mono: 'dari Yogyakarta, di bawah langit penuh bintang',
    },
    misc: { moreProjects: 'lihat semua', lessProjects: 'tutup arsip' },
  },
  en: {
    nav: { about: 'About', skills: 'Skills', journey: 'Journey', projects: 'Projects', contact: 'Contact' },
    hero: {
      eyebrow: 'Hi, I\u2019m',
      lead: 'Object detection research assistant at ITDA Yogyakarta; inventor on a CNN-based breast-cancer screening copyright; Bangkit Academy Distinction graduate (Cloud Computing). I build web apps — and occasionally simulate galaxies.',
      cta1: 'View Projects',
      cta2: 'Get in Touch',
      badgeResearch: 'Object Detection',
      badgeResearchSub: 'Computer Vision · ITDA',
      badgeDev: 'Software Developer',
      badgeDevSub: 'React · Three.js · Linux',
      location: 'Yogyakarta, Indonesia',
      open: 'Open to collaboration',
      scroll: 'Scroll',
    },
    roles: ['Object Detection Researcher', 'Machine Learning Engineer-in-Training', 'Web Developer', 'Linux & Kernel Tinkerer'],
    stats: { repos: 'Public Repositories', languages: 'Programming Languages', hki: 'Registered Patent (Inventor)', since: 'Coding Since' },
    section: {
      about: { num: '01', eyebrow: 'About me', title: 'An object detection researcher who builds software — from Yogyakarta.' },
      skills: { num: '02', eyebrow: 'Skills', title: 'The toolkit I reach for daily.' },
      journey: { num: '03', eyebrow: 'Journey', title: 'Research, industry, organizations — all in one timeline.' },
      projects: { num: '04', eyebrow: 'Projects', title: 'Things I have built along the way.' },
      contact: { num: '05', eyebrow: 'Contact', title: 'Let\u2019s connect.' },
    },
    about: {
      p1: 'I\u2019m an Informatics undergraduate at <strong>Institut Teknologi Dirgantara Adisutjipto (ITDA)</strong> Yogyakarta (2022–2026), currently researching <strong>object detection</strong>. Previously I joined a <strong>CNN-based breast cancer screening</strong> study that ended up as a registered copyright with me among the inventors.',
      p2: 'Outside the lab, I build web apps — from <strong>CodeIgniter 4</strong> to <strong>React + Three.js</strong> — and automate everything on Linux (ZRAM, dotfiles, kernels). I hold a <strong>Distinction Graduate</strong> credential for Bangkit Academy\u2019s Cloud Computing path plus a Dicoding professional certification.',
      p3: 'Community is part of who I am: <strong>IT Executive at Adisutjipto Linux Community</strong> and active in <strong>HMF ITDA</strong>. Other obsessions: aviation, outer space, and CTF puzzles.',
      terminalTitle: 'alif@itda:~$ whoami',
      education: 'Education',
      highlights: 'Highlights',
      honorBangkit: 'Bangkit Academy — Distinction (Cloud Computing, 2024)',
      honorHki: 'Inventor — Breast Cancer Screening copyright EC002024260420 (DJKI, 2024)',
      honorDicoding: 'Dicoding Professional Certification — Software Development (2024)',
    },
    journey: { work: 'Work & Research', education: 'Education', badgeResearch: 'Research', badgeWork: 'Industry', badgeOrg: 'Organization', badgeEdu: 'Education' },
    projects: { featured: 'Featured', archive: 'Other projects archive', visit: 'Live Demo', source: 'Source Code' },
    contact: {
      title: 'Let\u2019s connect.',
      desc: 'Interested in collaborating on computer vision research, a web project, or just chatting about tech? Reach me through these channels:',
    },
    footer: {
      built: 'Designed & built with Vite, React, TypeScript, and Three.js.',
      source: 'View source',
      mono: 'from Yogyakarta, under a sky full of stars',
    },
    misc: { moreProjects: 'view all', lessProjects: 'collapse archive' },
  },
} as const;

/** Perlebar literal string -> string agar kamus id & en bertipe sama */
type Widen<T> = T extends ReadonlyArray<infer U>
  ? ReadonlyArray<U>
  : { [K in keyof T]: T[K] extends string ? string : Widen<T[K]> };

export type Copy = Widen<(typeof copy)['id']>;
export default copy;
