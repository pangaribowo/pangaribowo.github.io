import { AppProvider } from './context'
import GalaxyScene from './components/GalaxyScene'
import { CursorAura } from './components/ui'
import Navbar from './components/Navbar'
import Hero from './components/Hero'
import { About, Skills, Stats } from './components/About'
import Journey from './components/Journey'
import Projects from './components/Projects'
import { Contact, Footer } from './components/Contact'

export default function App() {
  return (
    <AppProvider>
      <div className="aurora" aria-hidden="true" />
      <GalaxyScene />
      <div className="grain" aria-hidden="true" />
      <CursorAura />
      <Navbar />
      <main>
        <Hero />
        <Stats />
        <About />
        <Skills />
        <Journey />
        <Projects />
        <Contact />
      </main>
      <Footer />
    </AppProvider>
  )
}
