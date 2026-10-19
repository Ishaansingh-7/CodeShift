from ...tokens import Token
from ..c.lexer import OPS, Lexer

KEYWORDS = {
    "break", "case", "chan", "const", "continue", "default", "defer", "else", "fallthrough", "for", "func", "go", "goto",
    "if", "import", "interface", "map", "package", "range", "return", "select", "struct", "switch", "type", "var",
    "true", "false", "nil",
}
TYPES = {
    "int", "int8", "int16", "int32", "int64", "uint", "uint8", "uint16", "uint32", "uint64", "uintptr", "float32",
    "float64", "complex64", "complex128", "bool", "string", "rune", "byte", "error", "any",
}
BUILTINS = {"len", "cap", "append", "make", "new", "copy", "delete", "panic", "recover", "print", "println", "close",
            "min", "max", "clear"}
ENDS = {"break", "continue", "fallthrough", "return", "++", "--", ")", "]", "}"}


class GoLexer(Lexer):
    KEYWORDS, TYPES, BUILTINS, PRE = KEYWORDS, TYPES, BUILTINS, False
    OPS = [":=", "&^=", "&^", "<-"] + OPS

    def newline(self, at):
        t = self.toks[-1] if self.toks else None
        if t and t.line == self.line and (t.kind in ("NAME", "TYPE", "BUILTIN", "NUMBER", "STRING", "CHAR")
                                          or t.text in ENDS or t.text in ("true", "false", "nil")):
            self.toks.append(Token("PUNCT", ";", self.line, self.col(at)))
        super().newline(at)

    def op(self):
        if self.s[self.i] == "`":
            raise self.error("Unsupported: raw string literals", self.i)
        super().op()

    def run(self):
        toks = super().run()
        eof = toks.pop()
        self.newline(len(self.s))
        return self.toks + [eof]


def lex(code):
    return GoLexer(code).run()
