from ...tokens import Token
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
            self.template()
            return
        super().op()

    def template(self):
        s, start, line, bol = self.s, self.i, self.line, self.bol
        k, depth = self.i + 1, 0
        while True:
            if k >= len(s):
                raise self.error("Syntax error: unterminated template literal", start)
            c = s[k]
            if c == "\\":
                k += 2
                continue
            if c == "\n":
                self.newline(k)
            if depth == 0 and c == "`":
                break
            if s.startswith("${", k):
                depth += 1
                k += 2
                continue
            if depth and c == "}":
                depth -= 1
            k += 1
        self.toks.append(Token("TEMPLATE", s[start:k + 1], line, start - bol + 1))
        self.i = k + 1


def lex(code):
    return JSLexer(code).run()
