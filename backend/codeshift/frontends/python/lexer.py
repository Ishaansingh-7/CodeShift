from ...errors import CompileError
from ...tokens import Token

KEYWORDS = {
    "def", "return", "if", "elif", "else", "while", "for", "in", "and", "or", "not", "True", "False", "None",
    "pass", "break", "continue", "import", "from", "class", "lambda", "global", "nonlocal", "try", "except",
    "finally", "with", "as", "yield", "del", "assert", "raise", "is", "async", "await",
}
TYPES = {"int", "bool", "str", "list", "float"}
BUILTINS = {"print", "range", "len"}
OPS = [
    "**=", "//=", ">>=", "<<=", "==", "!=", "<=", ">=", "//", "**", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "->", "<<", ">>", ":=", "+", "-", "*", "/", "%", "<", ">", "=", "&", "|", "^", "~", "@",
]
PUNCT = "()[]{},:.;"
CLOSE = {")": "(", "]": "[", "}": "{"}
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", "'": "'", '"': '"'}


def lex(code):
    return Lexer(code).run()


def unquote(text):
    q = text[0]
    n = 3 if text.startswith(q * 3) else 1
    body = text[n:-n]
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            e = body[i + 1]
            if e == "\n":
                i += 2
                continue
            if e not in ESCAPES:
                raise ValueError(e)
            out.append(ESCAPES[e])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


class Lexer:
    def __init__(self, code):
        self.s = code.replace("\r\n", "\n").replace("\r", "\n")
        self.i = 0
        self.line = 1
        self.bol = 0
        self.toks = []
        self.indents = [0]
        self.brackets = []
        self.bol_pending = True

    def add(self, kind, text, start):
        self.toks.append(Token(kind, text, self.line, start - self.bol + 1))

    def error(self, msg, at=None):
        return CompileError("lexer", msg, self.line, (self.i if at is None else at) - self.bol + 1)

    def run(self):
        s = self.s
        while self.i < len(s):
            if self.bol_pending:
                self.bol_pending = self.indentation()
                continue
            c = s[self.i]
            if c in " \t\f":
                self.i += 1
            elif c == "#":
                while self.i < len(s) and s[self.i] != "\n":
                    self.i += 1
            elif c == "\\" and s.startswith("\\\n", self.i):
                self.i += 2
                self.line += 1
                self.bol = self.i
            elif c == "\n":
                if not self.brackets:
                    self.add("NEWLINE", "\n", self.i)
                    self.bol_pending = True
                self.i += 1
                self.line += 1
                self.bol = self.i
            elif c.isdigit() or (c == "." and self.i + 1 < len(s) and s[self.i + 1].isdigit()):
                self.number()
            elif c.isalpha() or c == "_":
                self.word()
            elif c in "\"'":
                self.string()
            else:
                self.op()
        if self.brackets:
            ch, line, col = self.brackets[-1]
            raise CompileError("lexer", f"Syntax error: '{ch}' is never closed", line, col)
        if self.toks and self.toks[-1].kind != "NEWLINE":
            self.add("NEWLINE", "\n", self.i)
        while len(self.indents) > 1:
            self.indents.pop()
            self.add("DEDENT", "", self.i)
        self.add("EOF", "", self.i)
        return self.toks

    def indentation(self):
        s = self.s
        j = self.i
        width = 0
        while j < len(s) and s[j] in " \t\f":
            width = width + 1 if s[j] == " " else (width // 8 + 1) * 8 if s[j] == "\t" else 0
            j += 1
        if j >= len(s):
            self.i = j
            return True
        if s[j] in "\n#":
            while j < len(s) and s[j] != "\n":
                j += 1
            self.i = j + 1 if j < len(s) else j
            if j < len(s):
                self.line += 1
                self.bol = self.i
            return True
        if width > self.indents[-1]:
            self.indents.append(width)
            self.add("INDENT", s[self.i:j], self.i)
        elif width < self.indents[-1]:
            while width < self.indents[-1]:
                self.indents.pop()
                self.add("DEDENT", "", j)
            if width != self.indents[-1]:
                raise self.error("Indentation error: unindent does not match any outer indentation level", j)
        self.i = j
        return False

    def number(self):
        s, start = self.s, self.i
        j = start
        if s[j] == "0" and j + 1 < len(s) and s[j + 1] in "xXoObB":
            j += 2
            while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                j += 1
        else:
            while j < len(s) and (s[j].isdigit() or s[j] == "_"):
                j += 1
            if j < len(s) and s[j] == ".":
                j += 1
                while j < len(s) and s[j].isdigit():
                    j += 1
            if j < len(s) and s[j] in "eE":
                j += 1
                if j < len(s) and s[j] in "+-":
                    j += 1
                while j < len(s) and s[j].isdigit():
                    j += 1
            if j < len(s) and s[j] in "jJ":
                j += 1
        if j < len(s) and (s[j].isalpha() or s[j] == "_"):
            raise self.error(f"Syntax error: invalid number '{s[start:j + 1]}'", start)
        self.add("NUMBER", s[start:j], start)
        self.i = j

    def word(self):
        s, start = self.s, self.i
        j = start
        while j < len(s) and (s[j].isalnum() or s[j] == "_"):
            j += 1
        w = s[start:j]
        if j < len(s) and s[j] in "\"'" and w.lower() == "f":
            self.i = j
            self.string()
            tok = self.toks.pop()
            self.toks.append(Token("FSTRING", tok.text, tok.line, start - self.bol + 1))
            return
        if j < len(s) and s[j] in "\"'" and w.lower() in {"f", "r", "b", "u", "rb", "br", "fr", "rf"}:
            raise CompileError("lexer", f"Unsupported: string prefix '{w}'", self.line, start - self.bol + 1)
        kind = "KEYWORD" if w in KEYWORDS else "TYPE" if w in TYPES else "BUILTIN" if w in BUILTINS else "NAME"
        self.add(kind, w, start)
        self.i = j

    def string(self):
        s, start = self.s, self.i
        q = s[start]
        triple = s.startswith(q * 3, start)
        line, col = self.line, start - self.bol + 1
        j = start + (3 if triple else 1)
        while True:
            if j >= len(s):
                raise CompileError("lexer", "Syntax error: unterminated string", line, col)
            c = s[j]
            if c == "\\" and j + 1 < len(s):
                if s[j + 1] == "\n":
                    self.line += 1
                    self.bol = j + 2
                j += 2
                continue
            if triple and s.startswith(q * 3, j):
                j += 3
                break
            if not triple and c == q:
                j += 1
                break
            if c == "\n":
                if not triple:
                    raise CompileError("lexer", "Syntax error: unterminated string", line, col)
                self.line += 1
                self.bol = j + 1
            j += 1
        self.toks.append(Token("STRING", s[start:j], line, col))
        self.i = j

    def op(self):
        s, start = self.s, self.i
        for op in OPS:
            if s.startswith(op, start):
                self.add("OP", op, start)
                self.i += len(op)
                return
        c = s[start]
        if c not in PUNCT:
            raise self.error(f"Syntax error: unexpected character '{c}'")
        if c in "([{":
            self.brackets.append((c, self.line, start - self.bol + 1))
        elif c in CLOSE:
            if not self.brackets or self.brackets[-1][0] != CLOSE[c]:
                raise self.error(f"Syntax error: unmatched '{c}'")
            self.brackets.pop()
        self.add("PUNCT", c, start)
        self.i += 1
