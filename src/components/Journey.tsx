import { useApp } from '../context'
import { education, experience } from '../data/portfolio'
import type { ExpKind, ExperienceItem } from '../data/portfolio'
import { Reveal, SectionHead } from './ui'

const KIND_ICON: Record<ExpKind, string> = {
  research: 'research',
  work: 'work',
  org: 'org',
  edu: 'edu',
}

function Timeline({ items }: { items: ExperienceItem[] }) {
  const { t, lang } = useApp()
  const badge: Record<ExpKind, string> = {
    research: t.journey.badgeResearch,
    work: t.journey.badgeWork,
    org: t.journey.badgeOrg,
    edu: t.journey.badgeEdu,
  }
  return (
    <div className="tl">
      {items.map((item, i) => (
        <Reveal key={i} delay={Math.min(i * 0.06, 0.3)}>
          <div className="tl-item">
            <span className="tl-date">{item.period[lang]}</span>
            <h3>{item.title[lang]}</h3>
            <div className="tl-org">{item.org}</div>
            <p>{item.desc[lang]}</p>
            <div className="tl-tags">
              <span className={`kind ${KIND_ICON[item.kind]}`}>
                <span className="dot" aria-hidden="true" />
                {badge[item.kind]}
              </span>
              {item.tags?.map((tag) => <span className="mini-tag" key={tag}>{tag}</span>)}
            </div>
          </div>
        </Reveal>
      ))}
    </div>
  )
}

export default function Journey() {
  const { t } = useApp()
  return (
    <section className="block" id="perjalanan">
      <div className="wrap">
        <SectionHead num={t.section.journey.num} eyebrow={t.section.journey.eyebrow} title={t.section.journey.title} />
        <div className="about-grid" style={{ alignItems: 'start' }}>
          <div>
            <Reveal><span className="eyebrow" style={{ marginBottom: 20, display: 'inline-flex' }}>{t.journey.work}</span></Reveal>
            <Timeline items={experience} />
          </div>
          <div>
            <Reveal><span className="eyebrow" style={{ marginBottom: 20, display: 'inline-flex' }}>{t.about.education}</span></Reveal>
            <div className="tl">
              {education.map((item, i) => (
                <EducationCard key={i} item={item} idx={i} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function EducationCard({ item, idx }: { item: ExperienceItem; idx: number }) {
  const { t, lang } = useApp()
  return (
    <Reveal delay={Math.min(idx * 0.08, 0.3)}>
      <div className="tl-item">
        <span className="tl-date">{item.period[lang]}</span>
        <h3>{item.title[lang]}</h3>
        <div className="tl-org">{item.org}</div>
        <p>{item.desc[lang]}</p>
        <div className="tl-tags">
          <span className="kind edu"><span className="dot" aria-hidden="true" />{t.journey.badgeEdu}</span>
        </div>
      </div>
    </Reveal>
  )
}
