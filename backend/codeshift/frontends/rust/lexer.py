from ..c.lexer import OPS, Lexer

KEYWORDS = {
    "as", "break", "const", "continue", "crate", "else", "enum", "extern", "false", "fn", "for", "if", "impl", "in",
    "let", "loop", "match", "mod", "move", "mut", "pub", "ref", "return", "self", "Self", "static", "struct", "super",
    "trait", "true", "type", "unsafe", "use", "where", "while", "async", "await", "dyn",
}
TYPES = {"i8", "i16", "i32", "i64", "i128", "isize", "u8", "u16", "u32", "u64", "u128", "usize", "f32", "f64", "bool",
         "char", "str", "String", "Vec", "BTreeMap", "BTreeSet", "HashMap", "HashSet"}


class RustLexer(Lexer):
    KEYWORDS, TYPES, BUILTINS, PRE = KEYWORDS, TYPES, set(), False
    OPS = ["..=", "::", "=>", ".."] + OPS

    def number(self):
        s, start = self.s, self.i
        j = start
        while j < len(s) and (s[j].isalnum() or s[j] == "_"):
            j += 1
        if j + 1 < len(s) and s[j] == "." and s[j + 1].isdigit():
            j += 1
            while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                j += 1
        if s[j - 1] in "eE" and j + 1 < len(s) and s[j] in "+-" and s[j + 1].isdigit() \
                and not s[start:j].lower().startswith("0x"):
            j += 1
            while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                j += 1
        self.add("NUMBER", s[start:j], start)
        self.i = j

    def quoted(self, q):
        s, i = self.s, self.i
        if q == "'" and i + 2 < len(s) and s[i + 1] != "\\" and s[i + 2] != "'":
            raise self.error("Unsupported: lifetimes and labels", i)
        super().quoted(q)

    def op(self):
        if self.s[self.i] == "#":
            raise self.error("Unsupported: attributes", self.i)
        super().op()


def lex(code):
    return RustLexer(code).run()
