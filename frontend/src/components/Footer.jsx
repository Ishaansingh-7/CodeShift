export default function Footer() {
  return (
    <footer style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginTop: 28, color: '#7B8394', fontSize: 13 }}>
      <span>CodeShift · lexer → parser → semantic → IR → optimize → codegen</span>
      <span className="mono" style={{ fontSize: 12 }}>any ⇄ any · Python · C · Java · JavaScript · Go · Rust</span>
    </footer>
  )
}
