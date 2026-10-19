from ...errors import CompileError
from ...tokens import Token

KEYWORDS = {
    "if", "else", "while", "for", "do", "return", "break", "continue", "switch", "case", "default", "goto", "sizeof",
    "struct", "union", "enum", "typedef", "static", "extern", "const", "volatile", "register", "auto", "inline",
    "restrict", "true", "false", "NULL",
}
TYPES = {"int", "long", "char", "void", "short", "unsigned", "signed", "double", "float", "bool", "_Bool"}
BUILTINS = {"printf", "strlen", "puts", "putchar", "scanf", "malloc", "free", "strcmp", "strcpy", "strcat"}
OPS = [
    "<<=", ">>=", "...", "->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||", "+=", "-=", "*=", "/=", "%=",
    "&=", "|=", "^=", "+", "-", "*", "/", "%", "<", ">", "=", "!", "&", "|", "^", "~", "?", ":",
]
PUNCT = "()[]{},;."


def lex(code):
    return Lexer(code).run()


class Lexer:
    KEYWORDS, TYPES, BUILTINS, OPS, PRE = KEYWORDS, TYPES, BUILTINS, OPS, True

    def __init__(self, code):
        self.s = code.replace("\r\n", "\n").replace("\r", "\n")
        self.i = 0
        self.line = 1
        self.bol = 0
        self.toks = []

    def col(self, at):
        return at - self.bol + 1

    def add(self, kind, text, start):
        self.toks.append(Token(kind, text, self.line, self.col(start)))

    def error(self, msg, at):
        return CompileError("lexer", msg, self.line, self.col(at))

    def newline(self, at):
        self.line += 1
        self.bol = at + 1

    def run(self):
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if c == "\n":
                self.newline(self.i)
                self.i += 1
            elif c in " \t\f\v":
                self.i += 1
            elif s.startswith("//", self.i):
                while self.i < len(s) and s[self.i] != "\n":
                    self.i += 1
            elif s.startswith("/*", self.i):
                end = s.find("*/", self.i + 2)
                if end < 0:
                    raise self.error("Syntax error: unterminated comment", self.i)
                for k in range(self.i, end):
                    if s[k] == "\n":
                        self.newline(k)
                self.i = end + 2
            elif c == "#" and self.PRE and not s[self.bol:self.i].strip():
                start = self.i
                while self.i < len(s) and s[self.i] != "\n":
                    self.i += 1
                self.add("PRE", s[start:self.i].strip(), start)
            elif c.isdigit() or (c == "." and self.i + 1 < len(s) and s[self.i + 1].isdigit()):
                self.number()
            elif c.isalpha() or c == "_":
                self.word()
            elif c in "\"'":
                self.quoted(c)
            else:
                self.op()
        self.add("EOF", "", self.i)
        return self.toks

    def number(self):
        s, start = self.s, self.i
        j = start
        while j < len(s) and (s[j].isalnum() or s[j] in "._"):
            j += 1
            if s[j - 1] in "eE" and j < len(s) and s[j] in "+-" and not s[start:j].lower().startswith("0x"):
                j += 1
        self.add("NUMBER", s[start:j], start)
        self.i = j

    def word(self):
        s, start = self.s, self.i
        j = start
        while j < len(s) and (s[j].isalnum() or s[j] == "_"):
            j += 1
        w = s[start:j]
        kind = "KEYWORD" if w in self.KEYWORDS else "TYPE" if w in self.TYPES else "BUILTIN" if w in self.BUILTINS else "NAME"
        self.add(kind, w, start)
        self.i = j

    def quoted(self, q):
        s, start = self.s, self.i
        j = start + 1
        what = "string" if q == '"' else "character"
        while True:
            if j >= len(s) or s[j] == "\n":
                raise self.error(f"Syntax error: unterminated {what} literal", start)
            if s[j] == "\\":
                j += 2
                continue
            if s[j] == q:
                break
            j += 1
        self.add("STRING" if q == '"' else "CHAR", s[start:j + 1], start)
        self.i = j + 1

    def op(self):
        s, start = self.s, self.i
        for op in self.OPS:
            if s.startswith(op, start):
                self.add("OP", op, start)
                self.i += len(op)
                return
        if s[start] in PUNCT:
            self.add("PUNCT", s[start], start)
            self.i += 1
            return
        raise self.error(f"Syntax error: unexpected character '{s[start]}'", start)
