from ..c.lexer import OPS, Lexer

KEYWORDS = {
    "function", "let", "const", "var", "if", "else", "while", "for", "of", "in", "return", "true", "false", "null",
    "undefined", "new", "class", "do", "switch", "case", "default", "break", "continue", "typeof", "instanceof", "this",
    "try", "catch", "finally", "throw", "delete", "void", "yield", "async", "await", "import", "export",
}


class JSLexer(Lexer):
    KEYWORDS, TYPES, BUILTINS, PRE = KEYWORDS, set(), set(), False
    OPS = ["===", "!==", "**=", ">>>=", ">>>", "**", "=>", "??", "?."] + OPS

    def quoted(self, q):
        super().quoted(q)
        t = self.toks[-1]
        if t.kind == "CHAR":
            self.toks[-1] = type(t)("STRING", t.text, t.line, t.col)

    def op(self):
        if self.s[self.i] == "`":
            raise self.error("Unsupported: template literals", self.i)
        super().op()


def lex(code):
    return JSLexer(code).run()
