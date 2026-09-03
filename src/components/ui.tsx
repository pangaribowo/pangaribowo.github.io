import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { motion, useInView, useMotionValue, useSpring } from 'framer-motion'
import { useApp } from '../context'

/* ---------- Reveal: fade+slide saat elemen masuk viewport ---------- */
export function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-70px' }}
      transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1], delay }}
    >
      {children}
    </motion.div>
  )
}

/* ---------- SectionHead: nomor + judul + garis, ala portofolio dev ternama ---------- */
export function SectionHead({ num, eyebrow, title }: { num: string; eyebrow: string; title: string }) {
  return (
    <Reveal>
      <span className="eyebrow">{eyebrow}</span>
      <div className="sec-head" style={{ marginTop: 12 }}>
        <span className="sec-num">{num}</span>
        <h2 className="sec-title">{title}</h2>
        <div className="sec-rule" />
      </div>
    </Reveal>
  )
}

/* ---------- Magnetic: tombol menempel halus ke kursor ---------- */
export function Magnetic({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const sx = useSpring(x, { stiffness: 180, damping: 14, mass: 0.4 })
  const sy = useSpring(y, { stiffness: 180, damping: 14, mass: 0.4 })

  return (
    <motion.div
      ref={ref}
      style={{ x: sx, y: sy, display: 'inline-block' }}
      onPointerMove={(e) => {
        const r = ref.current?.getBoundingClientRect()
        if (!r) return
        x.set((e.clientX - (r.left + r.width / 2)) * 0.28)
        y.set((e.clientY - (r.top + r.height / 2)) * 0.34)
      }}
      onPointerLeave={() => {
        x.set(0)
        y.set(0)
      }}
    >
      {children}
    </motion.div>
  )
}

/* ---------- TiltCard: kemiringan 3D mengikuti pointer (perangkat presisi saja) ---------- */
export function TiltCard({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const rx = useMotionValue(0)
  const ry = useMotionValue(0)
  const srx = useSpring(rx, { stiffness: 200, damping: 18 })
  const sry = useSpring(ry, { stiffness: 200, damping: 18 })
  const fine = matchMedia('(pointer: fine)').matches

  return (
    <motion.div
      ref={ref}
      className={className}
      style={{ rotateX: srx, rotateY: sry, transformStyle: 'preserve-3d', transformPerspective: 900 }}
      onPointerMove={(e) => {
        if (!fine) return
        const el = ref.current
        if (!el) return
        const r = el.getBoundingClientRect()
        ry.set(((e.clientX - r.left) / r.width - 0.5) * 7)
        rx.set(((e.clientY - r.top) / r.height - 0.5) * -7)
        el.style.setProperty('--mx', `${((e.clientX - r.left) / r.width) * 100}%`)
        el.style.setProperty('--my', `${((e.clientY - r.top) / r.height) * 100}%`)
      }}
      onPointerLeave={() => {
        rx.set(0)
        ry.set(0)
      }}
    >
      {children}
    </motion.div>
  )
}

/* ---------- CountUp: angka menaik saat terlihat ---------- */
export function CountUp({ value, suffix = '', plain = false }: { value: number; suffix?: string; plain?: boolean }) {
  const ref = useRef<HTMLElement>(null)
  const inView = useInView(ref, { once: true, margin: '-40px' })
  const [n, setN] = useState(0)

  useEffect(() => {
    if (!inView) return
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setN(value)
      return
    }
    const t0 = performance.now()
    const dur = 1500
    let raf = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / dur)
      setN(Math.round(value * (1 - Math.pow(1 - p, 3))))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [inView, value])

  return (
    <b ref={ref}>
      <span>{plain ? value : n}</span>
      {!plain && suffix}
    </b>
  )
}

/* ---------- TypedRoles: efek mesin ketik untuk deretan peran ---------- */
export function TypedRoles() {
  const { t } = useApp()
  const [text, setText] = useState('')
  const roles = t.roles

  useEffect(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setText(roles[0])
      return
    }
    let ri = 0
    let ci = 0
    let del = false
    let timer: number
    const step = () => {
      const word = roles[ri % roles.length]
      if (!del) {
        ci++
        setText(word.slice(0, ci))
        if (ci >= word.length) {
          del = true
          timer = window.setTimeout(step, 1900)
          return
        }
        timer = window.setTimeout(step, 62)
      } else {
        ci--
        setText(word.slice(0, ci))
        if (ci <= 0) {
          del = false
          ri++
          timer = window.setTimeout(step, 380)
          return
        }
        timer = window.setTimeout(step, 30)
      }
    }
    timer = window.setTimeout(step, 350)
    return () => clearTimeout(timer)
  }, [roles])

  return (
    <div className="role-line" aria-live="polite">
      <span>{text}</span>
      <span className="cursor" aria-hidden="true">▊</span>
    </div>
  )
}

/* ---------- CursorAura: cahaya mengikuti kursor (desktop) ---------- */
export function CursorAura() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!matchMedia('(pointer: fine)').matches || matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const el = ref.current
    if (!el) return
    let raf = 0
    let cx = -999
    let cy = -999
    let tx = cx
    let ty = cy
    const move = (e: PointerEvent) => {
      tx = e.clientX
      ty = e.clientY
    }
    const loop = () => {
      cx += (tx - cx) * 0.12
      cy += (ty - cy) * 0.12
      el.style.transform = `translate(${cx - 280}px, ${cy - 280}px)`
      raf = requestAnimationFrame(loop)
    }
    addEventListener('pointermove', move, { passive: true })
    el.classList.add('on')
    raf = requestAnimationFrame(loop)
    return () => {
      removeEventListener('pointermove', move)
      cancelAnimationFrame(raf)
    }
  }, [])
  return <div ref={ref} className="cursor-aura" aria-hidden="true" />
}
