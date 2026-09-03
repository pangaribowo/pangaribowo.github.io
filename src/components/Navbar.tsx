import { useEffect, useState } from 'react'
import { motion, useScroll, useSpring } from 'framer-motion'
import { Github, Linkedin, Menu, Moon, Sun, X } from 'lucide-react'
import { useApp } from '../context'
import { profile } from '../data/portfolio'

const SECTIONS = [
  { id: 'tentang', num: '01', key: 'about' },
  { id: 'keahlian', num: '02', key: 'skills' },
  { id: 'perjalanan', num: '03', key: 'journey' },
  { id: 'proyek', num: '04', key: 'projects' },
  { id: 'kontak', num: '05', key: 'contact' },
] as const

export default function Navbar() {
  const { theme, toggleTheme, lang, setLang, t } = useApp()
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState('')
  const { scrollYProgress } = useScroll()
  const progress = useSpring(scrollYProgress, { stiffness: 120, damping: 26 })

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: '-40% 0px -55% 0px' },
    )
    SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id)
      if (el) io.observe(el)
    })
    return () => io.disconnect()
  }, [])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    const onResize = () => {
      if (window.innerWidth > 860) setOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return (
    <>
      <motion.div className="progress" style={{ scaleX: progress }} />
      {open && (
        <div
          className="nav-backdrop"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}
      <nav className="nav">
        <div className="nav-in">
          <a className="brand" href="#atas" onClick={() => setOpen(false)}>
            <span className="brand-dot">FA</span>
            <span>pangaribowo <em>.io</em></span>
          </a>
          <ul className={`nav-links${open ? ' open' : ''}`}>
            {SECTIONS.map(({ id, num, key }) => (
              <li key={id}>
                <a href={`#${id}`} className={active === id ? 'active' : ''} onClick={() => setOpen(false)}>
                  <span className="n">{num}.</span>
                  {t.nav[key]}
                </a>
              </li>
            ))}
          </ul>
          <div className="nav-actions">
            <button
              className="icon-btn lang-btn"
              onClick={() => setLang(lang === 'id' ? 'en' : 'id')}
              aria-label={lang === 'id' ? 'Ganti ke Bahasa Inggris' : 'Switch to Indonesian'}
            >
              <span className={lang === 'id' ? 'on' : ''}>ID</span>·<span className={lang === 'en' ? 'on' : ''}>EN</span>
            </button>
            <button
              className="icon-btn"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Mode siang' : 'Mode gelap'}
            >
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button
              className="icon-btn burger"
              onClick={() => setOpen((v) => !v)}
              aria-label={open ? (lang === 'id' ? 'Tutup navigasi' : 'Close navigation') : (lang === 'id' ? 'Buka navigasi' : 'Open navigation')}
              aria-expanded={open}
            >
              {open ? <X size={17} /> : <Menu size={17} />}
            </button>
          </div>
        </div>
      </nav>

      {/* Side rails — konvensi portofolio dev ternama */}
      <div className="rail left" aria-hidden="true">
        <a href={profile.socials.github} target="_blank" rel="noopener" aria-label="GitHub"><Github size={19} /></a>
        <a href={profile.socials.linkedin} target="_blank" rel="noopener" aria-label="LinkedIn"><Linkedin size={19} /></a>
      </div>
      <div className="rail right" aria-hidden="true">
        <span className="vertical">FATAHILLAH ALIF PANGARIBOWO</span>
      </div>
    </>
  )
}
