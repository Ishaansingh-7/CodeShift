import { useEffect, useRef } from 'react'
import monaco from '../monaco.js'

export default function SourceEditor({ value, language, height, onChange, onHoverLine, highlight, error }) {
  const host = useRef(null)
  const ed = useRef(null)
  const decos = useRef(null)
  const applying = useRef(false)
  const handlers = useRef({})
  handlers.current = { onChange, onHoverLine }

  useEffect(() => {
    const editor = monaco.editor.create(host.current, {
      value, language, theme: 'codeshift', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, lineHeight: 22,
      minimap: { enabled: false }, scrollBeyondLastLine: false, automaticLayout: true, renderLineHighlight: 'none',
      padding: { top: 12, bottom: 12 }, lineNumbersMinChars: 4, glyphMargin: false, folding: false, overviewRulerLanes: 0,
      hideCursorInOverviewRuler: true, guides: { indentation: false }, tabSize: language === 'javascript' ? 2 : 4,
      scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8, useShadows: false }, fixedOverflowWidgets: true,
      contextmenu: true, wordBasedSuggestions: 'off', quickSuggestions: false,
    })
    ed.current = editor
    decos.current = editor.createDecorationsCollection()
    editor.onDidChangeModelContent(() => { if (!applying.current) handlers.current.onChange(editor.getValue()) })
    editor.onMouseMove(e => handlers.current.onHoverLine(e.target.position?.lineNumber ?? null))
    editor.onMouseLeave(() => handlers.current.onHoverLine(null))
    return () => editor.dispose()
  }, [])

  useEffect(() => {
    const editor = ed.current
    if (!editor || editor.getValue() === value) return
    applying.current = true
    editor.setValue(value)
    applying.current = false
  }, [value])

  useEffect(() => {
    const model = ed.current?.getModel()
    if (!model) return
    monaco.editor.setModelLanguage(model, language)
    model.updateOptions({ tabSize: language === 'javascript' ? 2 : 4 })
  }, [language])

  useEffect(() => {
    const model = ed.current?.getModel()
    if (!model) return
    const items = (highlight || []).map(n => ({
      range: new monaco.Range(n, 1, n, 1),
      options: { isWholeLine: true, className: 'cs-hl-src', lineNumberClassName: 'cs-hl-gut-src' },
    }))
    if (error?.line) {
      items.push({ range: new monaco.Range(error.line, 1, error.line, 1), options: { isWholeLine: true, className: 'cs-err-line', linesDecorationsClassName: 'cs-err-gut' } })
    }
    decos.current.set(items)
    const lines = model.getLineCount()
    monaco.editor.setModelMarkers(model, 'codeshift', error?.line && error.line <= lines ? [{
      severity: monaco.MarkerSeverity.Error, message: error.message, startLineNumber: error.line,
      startColumn: Math.max(1, error.col), endLineNumber: error.line, endColumn: Math.max(error.col + 1, model.getLineMaxColumn(error.line)),
    }] : [])
  }, [highlight, error, value])

  return <div ref={host} style={{ height, width: '100%' }} />
}
