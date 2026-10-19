import * as monaco from 'monaco-editor/editor/editor.api'
import 'monaco-editor/editor/contrib/bracketMatching/browser/bracketMatching'
import 'monaco-editor/editor/contrib/clipboard/browser/clipboard'
import 'monaco-editor/editor/contrib/comment/browser/comment'
import 'monaco-editor/editor/contrib/contextmenu/browser/contextmenu'
import 'monaco-editor/editor/contrib/indentation/browser/indentation'
import 'monaco-editor/editor/contrib/linesOperations/browser/linesOperations'
import 'monaco-editor/editor/contrib/multicursor/browser/multicursor'
import 'monaco-editor/editor/contrib/wordHighlighter/browser/wordHighlighter'
import 'monaco-editor/features/find/register'
import 'monaco-editor/languages/definitions/python/register'
import 'monaco-editor/languages/definitions/cpp/register'
import 'monaco-editor/languages/definitions/java/register'
import 'monaco-editor/languages/definitions/javascript/register'
import 'monaco-editor/languages/definitions/go/register'
import 'monaco-editor/languages/definitions/rust/register'
import '../node_modules/monaco-editor/esm/vs/base/browser/ui/codicons/codicon/codicon.css'
import EditorWorker from 'monaco-editor/editor/editor.worker?worker'

self.MonacoEnvironment = { getWorker: () => new EditorWorker() }

monaco.editor.defineTheme('codeshift', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: '', foreground: 'DDE1E7' },
    { token: 'keyword', foreground: 'C792EA' },
    { token: 'type', foreground: '7FDBCA' },
    { token: 'type.identifier', foreground: '7FDBCA' },
    { token: 'string', foreground: 'C3E88D' },
    { token: 'number', foreground: 'F78C6C' },
    { token: 'comment', foreground: '5E6674', fontStyle: 'italic' },
    { token: 'delimiter', foreground: '8E97A6' },
    { token: 'operator', foreground: '8E97A6' },
    { token: 'identifier', foreground: 'DDE1E7' },
    { token: 'keyword.directive', foreground: '89DDFF' },
    { token: 'annotation', foreground: '89DDFF' },
  ],
  colors: {
    'editor.background': '#11141A',
    'editor.foreground': '#DDE1E7',
    'editorLineNumber.foreground': '#4A5260',
    'editorLineNumber.activeForeground': '#A3ABB9',
    'editor.lineHighlightBackground': '#00000000',
    'editor.lineHighlightBorder': '#00000000',
    'editorCursor.foreground': '#FFA657',
    'editor.selectionBackground': '#2A3B55',
    'editorIndentGuide.background1': '#1F242D',
    'editorWidget.background': '#151920',
    'scrollbarSlider.background': '#262B3580',
  },
})

export default monaco
