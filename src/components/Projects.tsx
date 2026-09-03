import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowUpRight, ChevronDown, Code2, FolderOpen, Github, Orbit, ScanFace, TrendingUp } from 'lucide-react'
import { useApp } from '../context'
import { projects } from '../data/portfolio'
import { Reveal, SectionHead, TiltCard } from './ui'

const GLYPHS = [Code2, ScanFace, Orbit, TrendingUp]

export default function Projects() {
  const { t, lang } = useApp()
  const featured = projects.filter((p) => p.featured)
  const archive = projects.filter((p) => !p.featured)
  const [showAll, setShowAll] = useState(false)

  return (
    <section className="block" id="proyek">
      <div className="wrap">
        <SectionHead num={t.section.projects.num} eyebrow={t.section.projects.eyebrow} title={t.section.projects.title} />

        <div className="feat-list">
          {featured.map((p, i) => {
            const Glyph = GLYPHS[i % GLYPHS.length]
            return (
              <Reveal key={p.name} delay={0.05}>
                <TiltCard className="feat glass">
                  <div className="feat-visual" aria-hidden="true">
                    <Glyph className="glyph" strokeWidth={1.1} />
                  </div>
                  <div className="feat-body">
                    <div className="feat-over">{t.projects.featured} — {String(i + 1).padStart(2, '0')}</div>
                    <h3>{p.name}</h3>
                    <p>{p.desc[lang]}</p>
                    <div className="feat-links">
                      {p.live && (
                        <a href={p.live} target="_blank" rel="noopener">
                          {t.projects.visit} <ArrowUpRight size={15} />
                        </a>
                      )}
                      <a href={p.repo} target="_blank" rel="noopener">
                        {t.projects.source} <Github size={15} />
                      </a>
                    </div>
                  </div>
                </TiltCard>
              </Reveal>
            )
          })}
        </div>

        <Reveal>
          <div style={{ marginTop: 44 }}>
            <span className="eyebrow" style={{ display: 'inline-flex' }}>{t.projects.archive}</span>
          </div>
        </Reveal>
        <div className="proj-grid" style={{ marginTop: 20 }}>
          {archive.slice(0, showAll ? archive.length : 6).map((p, i) => (
            <Reveal key={p.name} delay={Math.min(i * 0.05, 0.25)}>
              <div className="pcard glass glass-hover">
                <div className="pcard-top">
                  <FolderOpen />
                  <a href={p.repo} target="_blank" rel="noopener" aria-label={`${p.name} — GitHub`}><Github size={17} /></a>
                </div>
                <h3><a href={p.repo} target="_blank" rel="noopener">{p.name}</a></h3>
                <p>{p.desc[lang]}</p>
                <div className="tech">{p.stack.map((s) => <span key={s}>{s}</span>)}</div>
              </div>
            </Reveal>
          ))}
        </div>

        <AnimatePresence>
          <motion.div className="archive-toggle" layout>
            <button onClick={() => setShowAll((v) => !v)}>
              {showAll ? t.misc.lessProjects : t.misc.moreProjects}
              <motion.span animate={{ rotate: showAll ? 180 : 0 }} style={{ display: 'inline-flex' }}>
                <ChevronDown size={15} />
              </motion.span>
            </button>
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  )
}
