import { motion } from 'framer-motion'
import { ArrowDownRight, BrainCircuit, Braces, MapPin, Sparkles } from 'lucide-react'
import { useApp } from '../context'
import { profile } from '../data/portfolio'
import { Magnetic, TypedRoles } from './ui'

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09, delayChildren: 0.15 } },
}
const item = {
  hidden: { opacity: 0, y: 26 },
  show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] as const } },
}

export default function Hero() {
  const { t } = useApp()
  return (
    <header className="hero" id="atas">
      <div className="wrap hero-grid">
        <motion.div variants={container} initial="hidden" animate="show">
          <motion.span className="eyebrow" variants={item}>{t.hero.eyebrow}</motion.span>
          <motion.h1 variants={item}>
            Fatahillah Alif <span className="grad">Pangaribowo</span>
          </motion.h1>
          <motion.div variants={item}><TypedRoles /></motion.div>
          <motion.p className="hero-lead" variants={item}>{t.hero.lead}</motion.p>

          <motion.div className="hero-actions" variants={item}>
            <Magnetic>
              <a className="btn btn-primary" href="#proyek">
                {t.hero.cta1} <ArrowDownRight size={16} />
              </a>
            </Magnetic>
            <Magnetic>
              <a className="btn btn-ghost" href="#kontak">{t.hero.cta2}</a>
            </Magnetic>
          </motion.div>

          <motion.div className="hero-pills" variants={item}>
            <span className="pill"><MapPin /> {t.hero.location}</span>
            <span className="pill"><Sparkles /> {t.hero.open}</span>
          </motion.div>
        </motion.div>

        <motion.div
          className="orbit-box"
          initial={{ opacity: 0, scale: 0.86 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.35 }}
        >
          <div className="orbit-ring" aria-hidden="true" />
          <div className="orbit-ring r2" aria-hidden="true" />
          <img className="orbit-img" src={profile.avatar} alt="Foto Fatahillah Alif Pangaribowo" width={330} height={330} />
          <div className="orbit-chip glass oc1">
            <span className="ic"><BrainCircuit /></span>
            <span><b>{t.hero.badgeResearch}</b><small>{t.hero.badgeResearchSub}</small></span>
          </div>
          <div className="orbit-chip glass oc2">
            <span className="ic"><Braces /></span>
            <span><b>{t.hero.badgeDev}</b><small>{t.hero.badgeDevSub}</small></span>
          </div>
        </motion.div>
      </div>
      <div className="scroll-hint" aria-hidden="true">{t.hero.scroll}</div>
    </header>
  )
}
