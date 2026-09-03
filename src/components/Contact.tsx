import { Github, Linkedin, Sparkles } from 'lucide-react'
import { useApp } from '../context'
import { profile } from '../data/portfolio'
import { Magnetic, Reveal, SectionHead } from './ui'

export function Contact() {
  const { t } = useApp()
  return (
    <section className="block" id="kontak">
      <div className="wrap">
        <SectionHead num={t.section.contact.num} eyebrow={t.section.contact.eyebrow} title={t.section.contact.title} />
        <Reveal>
          <div className="contact-hero glass">
            <h2>{t.contact.title}</h2>
            <p>{t.contact.desc}</p>
            <div className="socials">
              <Magnetic>
                <a className="soc" href={profile.socials.github} target="_blank" rel="noopener">
                  <Github /> GitHub <small>@pangaribowo</small>
                </a>
              </Magnetic>
              <Magnetic>
                <a className="soc" href={profile.socials.linkedin} target="_blank" rel="noopener">
                  <Linkedin /> LinkedIn <small>/in/fatahillahalif</small>
                </a>
              </Magnetic>
              <Magnetic>
                <a className="soc" href={profile.socials.githubAlt} target="_blank" rel="noopener">
                  <Sparkles /> GitHub <small>@oalalif</small>
                </a>
              </Magnetic>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}

export function Footer() {
  const { t } = useApp()
  return (
    <footer>
      <div className="wrap">
        <p className="mono">{t.footer.mono}</p>
        <p>
          {t.footer.built}{' '}
          <a href="https://github.com/pangaribowo/pangaribowo.github.io" target="_blank" rel="noopener">
            {t.footer.source} →
          </a>
        </p>
        <p style={{ marginTop: 8 }}>© 2026 Fatahillah Alif Pangaribowo</p>
      </div>
    </footer>
  )
}
