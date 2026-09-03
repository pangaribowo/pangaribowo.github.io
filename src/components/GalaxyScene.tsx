import { memo, useEffect, useRef } from 'react'
import * as THREE from 'three'
import { useApp } from '../context'

/**
 * GalaxyScene — latar Three.js halaman.
 * Galaksi spiral partikel + kabut bintang jauh, rotasi lambat,
 * parallax mengikuti pointer, sadar tema gelap/terang,
 * hormat pada prefers-reduced-motion & pause saat tab tersembunyi.
 */
const GalaxyScene = memo(function GalaxyScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { theme } = useApp()
  const themeRef = useRef(theme)
  themeRef.current = theme

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
    } catch (e) {
      console.warn('WebGL is not supported or failed to initialize:', e)
      return
    }

    const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)').matches
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 100)
    camera.position.set(0, 2.6, 6.2)
    camera.lookAt(0, 0, 0)

    // --- Sprite partikel radial (tanpa aset eksternal) ---
    const spriteCanvas = document.createElement('canvas')
    spriteCanvas.width = spriteCanvas.height = 64
    const sctx = spriteCanvas.getContext('2d')
    if (!sctx) return

    const grad = sctx.createRadialGradient(32, 32, 0, 32, 32, 32)
    grad.addColorStop(0, 'rgba(255,255,255,1)')
    grad.addColorStop(0.35, 'rgba(255,255,255,0.6)')
    grad.addColorStop(1, 'rgba(255,255,255,0)')
    sctx.fillStyle = grad
    sctx.fillRect(0, 0, 64, 64)
    const sprite = new THREE.CanvasTexture(spriteCanvas)

    // --- Galaksi spiral ---
    const G_COUNT = 6500
    const gGeo = new THREE.BufferGeometry()
    const gPos = new Float32Array(G_COUNT * 3)
    const gCol = new Float32Array(G_COUNT * 3)
    const ARMS = 3
    const palette = [
      new THREE.Color('#7c6cff'),
      new THREE.Color('#41d9f2'),
      new THREE.Color('#7ef0c9'),
      new THREE.Color('#ffffff'),
    ]
    for (let i = 0; i < G_COUNT; i++) {
      const r = Math.pow(Math.random(), 0.7) * 4.2
      const armAngle = ((i % ARMS) / ARMS) * Math.PI * 2
      const spread = 0.35 + (r / 4.2) * 0.9
      const angle = armAngle + r * 1.15 + (Math.random() - 0.5) * spread
      const x = Math.cos(angle) * r + (Math.random() - 0.5) * 0.22
      const y = (Math.random() - 0.5) * 0.35 * (1 - r / 4.6)
      const z = Math.sin(angle) * r + (Math.random() - 0.5) * 0.22
      gPos.set([x, y, z], i * 3)
      const base = palette[i % palette.length]
      const mixed = base.clone().lerp(new THREE.Color('#7c6cff'), Math.min(1, r / 5))
      gCol.set([mixed.r, mixed.g, mixed.b], i * 3)
    }
    gGeo.setAttribute('position', new THREE.BufferAttribute(gPos, 3))
    gGeo.setAttribute('color', new THREE.BufferAttribute(gCol, 3))
    const gMat = new THREE.PointsMaterial({
      size: 0.055,
      map: sprite,
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const galaxy = new THREE.Points(gGeo, gMat)
    scene.add(galaxy)

    // --- Kabut bintang jauh ---
    const S_COUNT = 1200
    const sGeo = new THREE.BufferGeometry()
    const sPos = new Float32Array(S_COUNT * 3)
    for (let i = 0; i < S_COUNT; i++) {
      const radius = 12 + Math.random() * 26
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      sPos.set(
        [radius * Math.sin(phi) * Math.cos(theta), radius * Math.sin(phi) * Math.sin(theta) * 0.6, radius * Math.cos(phi)],
        i * 3,
      )
    }
    sGeo.setAttribute('position', new THREE.BufferAttribute(sPos, 3))
    const sMat = new THREE.PointsMaterial({
      size: 0.09,
      map: sprite,
      color: new THREE.Color('#9fb4ff'),
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const starfog = new THREE.Points(sGeo, sMat)
    scene.add(starfog)

    // --- Interaksi & loop ---
    let targetRX = 0
    let targetRY = 0
    let curRX = 0
    let curRY = 0
    const onPointer = (e: PointerEvent) => {
      targetRY = (e.clientX / window.innerWidth - 0.5) * 0.5
      targetRX = (e.clientY / window.innerHeight - 0.5) * 0.3
    }
    window.addEventListener('pointermove', onPointer, { passive: true })

    const resize = () => {
      camera.aspect = window.innerWidth / window.innerHeight
      camera.updateProjectionMatrix()
      renderer.setSize(window.innerWidth, window.innerHeight)
    }
    window.addEventListener('resize', resize)
    resize()

    let raf = 0
    let running = true
    const clock = new THREE.Clock()

    const tint = () => (themeRef.current === 'light' ? 0x8f92c9 : 0xffffff)

    const loop = () => {
      const dt = clock.getDelta()
      if (!prefersReduced) {
        galaxy.rotation.y += dt * 0.05
        starfog.rotation.y -= dt * 0.008
      }
      curRX += (targetRX - curRX) * 0.045
      curRY += (targetRY - curRY) * 0.045
      camera.position.x = curRY * 2.2
      camera.position.y = 2.6 + curRX * -1.4
      camera.lookAt(0, 0, 0)
      gMat.color.setHex(tint())
      sMat.color.setHex(themeRef.current === 'light' ? 0x7c86b8 : 0x9fb4ff)
      renderer.render(scene, camera)
      if (running) raf = requestAnimationFrame(loop)
    }
    loop()

    const onVisibility = () => {
      if (document.hidden) {
        running = false
        cancelAnimationFrame(raf)
      } else if (!running) {
        running = true
        clock.getDelta()
        loop()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      running = false
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onPointer)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibility)
      gGeo.dispose()
      sGeo.dispose()
      gMat.dispose()
      sMat.dispose()
      sprite.dispose()
      renderer.dispose()
    }
  }, [])

  return <canvas id="galaxy-canvas" ref={canvasRef} aria-hidden="true" />
})

export default GalaxyScene
