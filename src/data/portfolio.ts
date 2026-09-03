/* ============================================================
 * Data Profil & Portofolio — Fatahillah Alif Pangaribowo
 * Single source of truth untuk konten profil, riwayat, dan proyek
 * ============================================================ */


export type ExpKind = 'research' | 'work' | 'org' | 'edu';

export type Localized = { id: string; en: string };

export interface ExperienceItem {
  kind: ExpKind;
  period: Localized;
  title: Localized;
  org: string;
  desc: Localized;
  tags?: string[];
}

export interface ProjectItem {
  name: string;
  repo: string;
  live?: string;
  desc: { id: string; en: string };
  stack: string[];
  featured: boolean;
}

export const profile = {
  name: 'Fatahillah Alif Pangaribowo',
  short: 'Alif',
  location: 'Yogyakarta, Indonesia',
  avatar: 'https://avatars.githubusercontent.com/u/156567065?v=4',
  socials: {
    github: 'https://github.com/pangaribowo',
    githubAlt: 'https://github.com/oalalif',
    linkedin: 'https://www.linkedin.com/in/fatahillahalif',
  },
};

export const stats = [
  { value: 40, suffix: '+', key: 'repos' },
  { value: 9, suffix: '', key: 'languages' },
  { value: 1, suffix: '', key: 'hki' },
  { value: 2022, suffix: '', key: 'since', plain: true },
] as const;

export interface ExperienceData {
  experience: ExperienceItem[];
  education: ExperienceItem[];
  projects: ProjectItem[];
}

export const experience: ExperienceItem[] = [
  {
    kind: 'research',
    period: { id: '2025 — Sekarang', en: '2025 — Present' },
    title: { id: 'Object Detection Research Assistant', en: 'Object Detection Research Assistant' },
    org: 'Institut Teknologi Dirgantara Adisutjipto (ITDA) Yogyakarta',
    desc: {
      id: 'Riset computer vision: kurasi & anotasi dataset, pelatihan serta evaluasi model deteksi objek, dan dokumentasi pipeline eksperimen.',
      en: 'Computer vision research: dataset curation & annotation, training and evaluating object detection models, and documenting experiment pipelines.',
    },
    tags: ['Computer Vision', 'Deep Learning', 'Python'],
  },
  {
    kind: 'work',
    period: { id: '2025', en: '2025' },
    title: { id: 'Pengembang Web & Analis Sistem', en: 'Web Developer & System Analyst' },
    org: 'GMF AeroAsia',
    desc: {
      id: 'Pengalaman industri di lingkungan MRO kedirgantaraan: pengembangan web internal dan analisis sistem.',
      en: 'Industry experience in an aerospace MRO environment: internal web development and system analysis.',
    },
    tags: ['Web', 'System Analysis'],
  },
  {
    kind: 'org',
    period: { id: '2022 — Sekarang', en: '2022 — Present' },
    title: { id: 'IT Executive — Adisutjipto Linux Community', en: 'IT Executive — Adisutjipto Linux Community' },
    org: 'Adisutjipto Linux Community (ALC)',
    desc: {
      id: 'Mengelola infrastruktur TI komunitas open source kampus: administrasi sistem, dokumentasi, dan berbagi pengetahuan Linux.',
      en: 'Running IT infrastructure for the campus open-source community: system administration, documentation, and Linux knowledge sharing.',
    },
    tags: ['Linux', 'Open Source'],
  },
  {
    kind: 'research',
    period: { id: '2024', en: '2024' },
    title: { id: 'Asisten Riset — Deteksi Kanker Payudara Berbasis CNN', en: 'Research Assistant — CNN-based Breast Cancer Detection' },
    org: 'Institut Teknologi Dirgantara Adisutjipto (ITDA)',
    desc: {
      id: 'Riset penerapan Convolutional Neural Network untuk skrining kanker payudara. Berujung pada pencatatan HKI "Skrining Kanker Payudara" (No. EC002024260420, DJKI Kemdikti) dengan saya tercatat sebagai inventor.',
      en: 'Research on Convolutional Neural Networks for breast cancer screening. Culminated in the registered copyright "Skrining Kanker Payudara" (No. EC002024260420, DJKI) with me listed as an inventor.',
    },
    tags: ['CNN', 'Medical AI', 'HKI'],
  },
  {
    kind: 'edu',
    period: { id: '2024', en: '2024' },
    title: { id: 'Bangkit Academy — Cloud Computing (Lulusan Distinction)', en: 'Bangkit Academy — Cloud Computing (Distinction Graduate)' },
    org: 'Bangkit Academy led by Google, Tokopedia, Gojek & Traveloka',
    desc: {
      id: 'Menuntaskan jalur Cloud Computing dan lulus dengan predikat Distinction — hanya diberikan kepada kandidat dengan performa terbaik.',
      en: 'Completed the Cloud Computing path, graduating with Distinction — awarded only to top-performing candidates.',
    },
    tags: ['Google Cloud', 'Capstone'],
  },
  {
    kind: 'org',
    period: { id: '2024 — 2025', en: '2024 — 2025' },
    title: { id: 'Sekretaris MAKRAB Informatika 2024', en: 'Secretary — Informatika MAKRAB 2024' },
    org: 'HMF ITDA (Himpunan Mahasiswa Informatika)',
    desc: {
      id: 'Sekretariat kegiatan MAKRAB (Masa Keakraban) Informatika: administrasi acara, notulensi, dan koordinasi antar panitia.',
      en: 'Secretariat for the Informatics MAKRAB bonding event: event administration, minutes, and cross-committee coordination.',
    },
    tags: ['Leadership'],
  },
  {
    kind: 'work',
    period: { id: '2024', en: '2024' },
    title: { id: 'Koordinator Operasional & Eksekutif Produksi', en: 'Operations Coordinator & Production Executive' },
    org: 'UD Starfa Used Cooking Oil',
    desc: {
      id: 'Mengelola operasional dan produksi usaha pengolahan minyak jelantah — pengalaman kewirausahaan pertama.',
      en: 'Managed operations and production for a used cooking oil recycling venture — first hands-on entrepreneurship experience.',
    },
    tags: ['Operations'],
  },
];

export const education: ExperienceItem[] = [
  {
    kind: 'edu',
    period: { id: '2022 — 2026', en: '2022 — 2026' },
    title: { id: 'S1 Informatika', en: 'B.Sc. Informatics' },
    org: 'Institut Teknologi Dirgantara Adisutjipto (ITDA) Yogyakarta',
    desc: {
      id: 'Program sarjana Informatika di kampus kedirgantaraan kawasan Lanud Adisutjipto.',
      en: 'Undergraduate Informatics program at the aerospace institute near Adisutjipto Air Force Base.',
    },
  },
  {
    kind: 'edu',
    period: { id: '2024', en: '2024' },
    title: { id: 'Sertifikasi Profesional — Pengembangan Perangkat Lunak', en: 'Professional Certification — Software Development' },
    org: 'Dicoding Academy',
    desc: {
      id: 'Jalur sertifikasi pengembangan perangkat lunak; beberapa repo kursus & submission-nya masih tercatat di GitHub.',
      en: 'Software development certification track; several course and submission repos remain on GitHub.',
    },
  },
  {
    kind: 'edu',
    period: { id: '2019 — 2022', en: '2019 — 2022' },
    title: { id: 'MIPA — SMA Negeri 1 Pakem', en: 'Science — SMA Negeri 1 Pakem' },
    org: 'SMA Negeri 1 Pakem, Sleman',
    desc: {
      id: 'Jurusan Matematika & Ilmu Pengetahuan Alam di Kabupaten Sleman, Yogyakarta.',
      en: 'Mathematics & Natural Sciences track in Sleman, Yogyakarta.',
    },
  },
];

export const projects: ProjectItem[] = [
  {
    name: 'CodeIgniter MVC Workbench',
    repo: 'https://github.com/pangaribowo/codeigniter-mvc-workbench',
    desc: {
      id: 'Workbench offline-first untuk menguasai CodeIgniter 4: tracker pipeline visual request Router → Controller → Model → View, keystroke validation engine, dan kurikulum pembelajaran terstruktur.',
      en: 'An offline-first workbench for mastering CodeIgniter 4: visual request pipeline tracker (Router → Controller → Model → View), keystroke validation engine, and a structured learning curriculum.',
    },
    stack: ['CodeIgniter 4', 'PHP', 'Web Components', 'SPA'],
    featured: true,
  },
  {
    name: 'MLGC — Skin Classifier',
    repo: 'https://github.com/oalalif/mlgc',
    desc: {
      id: 'Aplikasi klasifikasi kondisi kulit: backend Hapi.js + TensorFlow.js di atas Google Cloud (Firestore + Storage), frontend drag-drop dengan riwayat prediksi.',
      en: 'Skin condition classification app: Hapi.js backend + TensorFlow.js on Google Cloud (Firestore + Storage), drag-drop frontend with prediction history.',
    },
    stack: ['TensorFlow.js', 'Hapi.js', 'GCP', 'Vanilla JS'],
    featured: true,
  },
  {
    name: 'Milkyway Explorer Pro',
    repo: 'https://github.com/oalalif/milkyway-explorer-pro',
    live: 'https://oalalif.github.io/milkyway-explorer-pro/',
    desc: {
      id: 'Simulasi 3D interaktif untuk menjelajah tata surya dan sekitarnya — visualisasi edukatif dengan kontrol eksplorasi lanjutan.',
      en: 'An interactive 3D simulation to explore the solar system and beyond — educational visualization with advanced exploration controls.',
    },
    stack: ['JavaScript', '3D', 'WebGL'],
    featured: true,
  },
  {
    name: 'Network Dashboard UI',
    repo: 'https://github.com/pangaribowo/network-dashboard-ui',
    desc: {
      id: 'Dashboard monitoring jaringan modern dan responsif dengan visualisasi Recharts di atas React + Tailwind CSS.',
      en: 'A modern, responsive network monitoring dashboard with Recharts visualizations on top of React + Tailwind CSS.',
    },
    stack: ['React', 'Tailwind CSS', 'Recharts'],
    featured: true,
  },
  {
    name: 'KPU Election System',
    repo: 'https://github.com/pangaribowo/kpu-election-system',
    desc: {
      id: 'Sistem pemungutan suara digital (TypeScript): manajemen pemilih, pemungutan, hingga rekapitulasi.',
      en: 'A TypeScript digital voting system: voter management, ballot casting, and result tabulation.',
    },
    stack: ['TypeScript'],
    featured: false,
  },
  {
    name: 'PostgreSQL E-commerce DB',
    repo: 'https://github.com/pangaribowo/postgresql-ecommerce-db',
    desc: {
      id: 'Desain skema relasional e-commerce ternormalisasi beserta query-nya di PostgreSQL.',
      en: 'Normalized relational e-commerce schema design with queries in PostgreSQL.',
    },
    stack: ['PostgreSQL', 'SQL'],
    featured: false,
  },
  {
    name: 'Pixel Hero Agents',
    repo: 'https://github.com/oalalif/pixel-hero-agents',
    desc: {
      id: 'Dashboard pixel-art top-down yang memvisualkan sesi Claude Code sebagai kantor mini berisi agen pekerja.',
      en: 'A top-down pixel-art dashboard visualizing Claude Code sessions as a tiny office of working agents.',
    },
    stack: ['Canvas', 'TypeScript'],
    featured: false,
  },
  {
    name: 'SystemOptimizer-ZRAM',
    repo: 'https://github.com/oalalif/SystemOptimizer-ZRAM',
    desc: {
      id: 'Skrip optimasi sistem Linux: konfigurasi ZRAM, tuning CPU, dan pembersihan rutin.',
      en: 'A Linux system optimization script: ZRAM setup, CPU tuning, and routine cleanup.',
    },
    stack: ['Shell', 'Linux'],
    featured: false,
  },
  {
    name: 'ThinkPad Kernel Tuning',
    repo: 'https://github.com/pangaribowo/thinkpad-windows-kernel-tuning',
    desc: {
      id: 'Otomatisasi tuning kernel Windows di ThinkPad memakai PowerShell.',
      en: 'Windows kernel tuning automation on ThinkPad using PowerShell.',
    },
    stack: ['PowerShell'],
    featured: false,
  },
  {
    name: 'Galaxy Explorer Pro',
    repo: 'https://github.com/oalalif/galaxy-explorer-pro',
    desc: {
      id: 'Eksplorasi galaksi dan benda langit imersif berbasis web 3D.',
      en: 'Immersive web-based 3D exploration of galaxies and celestial bodies.',
    },
    stack: ['JavaScript', '3D'],
    featured: false,
  },
  {
    name: 'Library Management System',
    repo: 'https://github.com/pangaribowo/library-management-system',
    desc: {
      id: 'Sistem manajemen perpustakaan berbasis Python.',
      en: 'A Python-based library management system.',
    },
    stack: ['Python'],
    featured: false,
  },
  {
    name: 'Rental Jeep Kaliurang',
    repo: 'https://github.com/pangaribowo/Rental-Jeep-Kaliurang',
    desc: {
      id: 'Aplikasi Java untuk layanan rental jeep wisata kawasan Kaliurang.',
      en: 'A Java application for jeep tour rentals in the Kaliurang highlands.',
    },
    stack: ['Java', 'OOP'],
    featured: false,
  },
  {
    name: 'Dotfiles & Neovim',
    repo: 'https://github.com/pangaribowo/dotfiles',
    desc: {
      id: 'Konfigurasi shell pribadi plus setup Neovim berbasis AstroNvim v4.',
      en: 'Personal shell configs plus an AstroNvim v4-based Neovim setup.',
    },
    stack: ['Shell', 'Lua'],
    featured: false,
  },
  {
    name: "What's In The Quantum",
    repo: 'https://github.com/oalalif/whats-in-the-quantum',
    desc: {
      id: 'Tantangan ala CTF bertema quantum — teka-teki interaktif di halaman web.',
      en: 'A quantum-themed CTF-style challenge — an interactive web puzzle.',
    },
    stack: ['CTF', 'HTML'],
    featured: false,
  },
];

export const skillGroups = [
  { icon: 'Code2', title: { id: 'Bahasa', en: 'Languages' }, items: ['Python', 'TypeScript', 'JavaScript', 'PHP', 'Java', 'Lua', 'SQL', 'Shell'] },
  { icon: 'Globe', title: { id: 'Web', en: 'Web' }, items: ['React', 'CodeIgniter 4', 'Node.js', 'Hapi.js', 'Tailwind CSS', 'Vite', 'HTML/CSS'] },
  { icon: 'BrainCircuit', title: { id: 'AI & Data', en: 'AI & Data' }, items: ['Computer Vision', 'CNN', 'TensorFlow.js', 'PostgreSQL', 'Anotasi Dataset', 'Firestore'] },
  { icon: 'TerminalSquare', title: { id: 'Sistem', en: 'Systems' }, items: ['Linux', 'Git & GitHub', 'Neovim', 'PowerShell', 'ZRAM', 'Google Cloud'] },
] as const;
