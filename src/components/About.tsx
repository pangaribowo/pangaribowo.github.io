import { Award, Code2, Globe, BrainCircuit, TerminalSquare, Medal, FileBadge, GraduationCap } from 'lucide-react'
import { useApp } from '../context'
import { stats, skillGroups } from '../data/portfolio'
import { CountUp, Reveal, SectionHead, TiltCard } from './ui'

const ICONS = { Code2, Globe, BrainCircuit, TerminalSquare } as const

export function Stats() {
  const { t } = useApp()
  return (
    <section className="block" style={{ paddingTop: 40, paddingBottom: 0 }} aria-label="Statistik">
      <div className="wrap">
        <Reveal>
          <div className="stats-grid">
            {stats.map((s) => (
              <div className="stat glass glass-hover" key={s.key}>
                <CountUp value={s.value} suffix={s.suffix} plain={'plain' in s} />
                <span>{t.stats[s.key as keyof typeof t.stats]}</span>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  )
}

function renderHonorText(text: string) {
  const parts = text.split('—')
  const title = parts[0]?.trim() || ''
  const detail = parts.slice(1).join('—').trim()
  return (
    <p>
      <b>{title}</b>
      {detail ? ` — ${detail}` : ''}
    </p>
  )
}

export function About() {
  const { t } = useApp()
  return (
    <section className="block" id="tentang">
      <div className="wrap">
        <SectionHead num={t.section.about.num} eyebrow={t.section.about.eyebrow} title={t.section.about.title} />
        <div className="about-grid">
          <Reveal>
            <p dangerouslySetInnerHTML={{ __html: t.about.p1 }} />
            <p dangerouslySetInnerHTML={{ __html: t.about.p2 }} />
            <p dangerouslySetInnerHTML={{ __html: t.about.p3 }} />
          </Reveal>
          <Reveal delay={0.12}>
            <div className="term glass">
              <div className="term-bar"><i /><i /><i /><span>{t.about.terminalTitle}</span></div>
              <pre>{`// profil ringkas
{
  role: "object detection ra",
  campus: "itda yogyakarta · 2022-2026",
  fokus: ["cv", "web", "linux"],
  hki: ["skrining kanker payudara"],
  predikat: "bangkit distinction",
  editor: "neovim + astronvim",
  open_to: ["riset", "kolaborasi web"]
}`}</pre>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.1}>
          <div style={{ marginTop: 28 }}>
            <span className="eyebrow" style={{ marginBottom: 14, display: 'inline-flex' }}>{t.about.highlights}</span>
            <div style={{ display: 'grid', gap: 10 }}>
              <div className="honor glass glass-hover">
                <FileBadge />
                {renderHonorText(t.about.honorHki)}
              </div>
              <div className="honor glass glass-hover">
                <Medal />
                {renderHonorText(t.about.honorBangkit)}
              </div>
              <div className="honor glass glass-hover">
                <Award />
                {renderHonorText(t.about.honorDicoding)}
              </div>
              <div className="honor glass glass-hover">
                <GraduationCap />
                <p><b>S1 Informatika ITDA</b> — 2022 — 2026 · SMAN 1 Pakem (MIPA, 2019 — 2022)</p>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}

export function Skills() {
  const { t, lang } = useApp()
  return (
    <section className="block" id="keahlian">
      <div className="wrap">
        <SectionHead num={t.section.skills.num} eyebrow={t.section.skills.eyebrow} title={t.section.skills.title} />
        <div className="skills-grid">
          {skillGroups.map((g, i) => {
            const Icon = ICONS[g.icon]
            return (
              <Reveal key={g.icon} delay={i * 0.08} className="reveal-wrap">
                <TiltCard className="skill-card glass">
                  <span className="skill-ic"><Icon /></span>
                  <h3>{g.title[lang]}</h3>
                  <div className="chips">{g.items.map((it) => <span className="chip" key={it}>{it}</span>)}</div>
                </TiltCard>
              </Reveal>
            )
          })}
        </div>
      </div>
    </section>
  )
}
