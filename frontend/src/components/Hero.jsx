import GlitchTitle from './GlitchTitle.jsx'
import HeroOrbit from './HeroOrbit.jsx'

export default function Hero({ src, tgt, srcFile, tgtFile, picker, actions }) {
  return (
    <div className="cs-hero">
      <div className="cs-hero-main">
        <h1 style={{ margin: 0, fontSize: 'clamp(26px, 3vw, 34px)', fontWeight: 650, letterSpacing: '-0.025em' }}>
          <span style={{ color: '#FFA657' }}>Shift</span> code between <span style={{ color: '#6CB6FF' }}>any</span> two languages.
        </h1>
        <GlitchTitle src={src} tgt={tgt} srcFile={srcFile} tgtFile={tgtFile} />
      </div>
      <HeroOrbit />
      <div className="cs-hero-pick">{picker}</div>
      <div className="cs-hero-acts">{actions}</div>
    </div>
  )
}
