from .. import ast as A
from ..errors import CompileError
from . import idioms

BINARY = {"||": 1, "&&": 2, "|": 3, "^": 4, "&": 5, "==": 6, "!=": 6, "===": 6, "!==": 6, "<": 7, "<=": 7, ">": 7,
          ">=": 7, "<<": 8, ">>": 8, "+": 9, "-": 9, "*": 10, "/": 10, "%": 10, "**": 11}
BOOL_TEXT = {("true", "false"): "b2s", ("True", "False"): "b2s_py"}
ASSIGN = {"=": None, "+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%"}
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", "'": "'", '"': '"'}
QUIET = {"NEWLINE", "INDENT", "DEDENT", "EOF"}


def unescape(body, tok, error):
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\":
            e = body[i + 1] if i + 1 < len(body) else ""
            if e not in ESCAPES:
                raise error(f"Unsupported: escape sequence '\\{e}'", tok)
            out.append(ESCAPES[e])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


class CFamily:
    lang = ""
    SLICE = None

    def __init__(self, toks):
        self.toks = toks
        self.i = 0
        self.last = toks[0]
        self.scopes = [set()]

    def declare_name(self, name, at):
        if any(name in s for s in self.scopes[:-1]):
            raise self.fail(f"Unsupported: redeclaring '{name}' inside an inner block (shadowing)", at)
        self.scopes[-1].add(name)

    def fresh_scopes(self, params):
        saved, self.scopes = self.scopes, [set(params)]
        return saved

    def peek(self, k=0):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def at(self, kind, text=None, k=0):
        t = self.peek(k)
        return t.kind == kind and (text is None or t.text == text)

    def at_op(self, *ops):
        t = self.peek()
        return t.kind in ("OP", "PUNCT") and t.text in ops

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        if t.kind not in QUIET:
            self.last = t
        return t

    def accept(self, kind, text=None):
        return self.next() if self.at(kind, text) else None

    def accept_op(self, *ops):
        return self.next() if self.at_op(*ops) else None

    def expect(self, kind, text=None, what=None):
        if self.at(kind, text):
            return self.next()
        raise self.error(f"expected {what or (repr(text) if text else kind.lower())}")

    def expect_op(self, op):
        if self.at_op(op):
            return self.next()
        raise self.error(f"expected '{op}'")

    def error(self, msg, tok=None):
        t = tok or self.peek()
        found = "end of file" if t.kind == "EOF" else repr(t.text)
        return CompileError("parser", f"Syntax error: {msg}, found {found}", t.line, t.col)

    def unsupported(self, what, tok=None):
        t = tok or self.peek()
        return CompileError("parser", f"Unsupported: {what}", t.line, t.col)

    def fail(self, msg, tok):
        return CompileError("parser", msg, tok.line, tok.col)

    def pos(self, t):
        return {"line": t.line, "col": t.col, "end": self.last.line}

    def block(self):
        self.expect_op("{")
        self.scopes.append(set())
        out = []
        while not self.at_op("}"):
            if self.at("EOF"):
                raise self.error("expected '}'")
            out += self.statement()
        self.next()
        self.scopes.pop()
        return out

    def body(self):
        return self.block() if self.at_op("{") else self.statement()

    def statement(self):
        t = self.peek()
        if self.at_op("{"):
            return self.block()
        if self.at_op(";"):
            self.next()
            return []
        if t.kind == "KEYWORD":
            if t.text == "if":
                return [self.if_stmt()]
            if t.text == "while":
                return [self.while_stmt()]
            if t.text == "for":
                return self.for_stmt()
            if t.text == "return":
                return [self.return_stmt()]
            if t.text in ("break", "continue"):
                self.next()
                self.end()
                return [(A.Break if t.text == "break" else A.Continue)(**self.pos(t))]
            if t.text in ("do", "switch", "goto", "case", "default", "try", "throw"):
                raise self.unsupported(f"'{t.text}' statement", t)
        if self.decl_start():
            out = self.declaration()
            self.end()
            return out
        out = self.simple()
        self.end()
        return out

    def end(self):
        self.expect_op(";")

    def if_stmt(self):
        t = self.next()
        test = self.cond()
        body = self.body()
        orelse = []
        if self.accept("KEYWORD", "else"):
            orelse = [self.if_stmt()] if self.at("KEYWORD", "if") else self.body()
        return A.If(test, body, orelse, **self.pos(t))

    def while_stmt(self):
        t = self.next()
        test = self.cond()
        return A.While(test, self.body(), **self.pos(t))

    def cond(self):
        self.expect_op("(")
        e = self.expr()
        self.expect_op(")")
        return e

    def for_stmt(self):
        self.scopes.append(set())
        try:
            return self.for_clauses()
        finally:
            self.scopes.pop()

    def for_clauses(self):
        t = self.next()
        self.expect_op("(")
        each = self.for_each(t)
        if each:
            return each
        init, scoped = None, False
        if not self.at_op(";"):
            if self.decl_start():
                decl = self.declaration()
                scoped = True
            else:
                decl = self.simple()
            if len(decl) != 1:
                raise self.unsupported("for-loop header with several declarations", t)
            init = decl[0]
        self.expect_op(";")
        cond = None if self.at_op(";") else self.loop_cond(self.expr())
        self.expect_op(";")
        update = None
        if not self.at_op(")"):
            ups = self.simple()
            if len(ups) != 1:
                raise self.unsupported("for-loop update with several statements", t)
            update = ups[0]
        self.expect_op(")")
        body = self.body()
        at = self.pos(t)
        for s in (init, update):
            if s is not None:
                s.line, s.col, s.end = t.line, t.col, t.line
        return idioms.make_for(init, cond, update, body, at, scoped)

    def for_each(self, t):
        return None

    def loop_cond(self, cond):
        return cond

    def return_stmt(self):
        t = self.next()
        value = None if self.at_op(";") else self.expr()
        self.end()
        return A.Return(value, **self.pos(t))

    def simple(self):
        t = self.peek()
        if self.at_op("++", "--"):
            op = self.next()
            target = self.target(self.unary())
            return [A.AugAssign(target, op.text[0], A.IntLit(1, line=t.line, col=t.col), **self.pos(t))]
        lhs = self.expr()
        if self.at_op(*ASSIGN):
            op = self.next()
            value = self.expr()
            if self.at_op(*ASSIGN):
                raise self.unsupported("chained assignment")
            return [self.assignment(lhs, op, value, t)]
        if self.at_op("++", "--"):
            op = self.next()
            return [A.AugAssign(self.target(lhs), op.text[0], A.IntLit(1, line=t.line, col=t.col), **self.pos(t))]
        return self.expr_statement(lhs, t)

    def assignment(self, lhs, op, value, t):
        if ASSIGN[op.text]:
            return A.AugAssign(self.target(lhs), ASSIGN[op.text], value, **self.pos(t))
        return A.Assign(self.target(lhs), value, **self.pos(t))

    def target(self, e):
        if isinstance(e, (A.Name, A.Index)):
            return e
        raise CompileError("parser", "Syntax error: cannot assign to this expression", e.line, e.col)

    def expr_statement(self, e, t):
        if isinstance(e, A.Call):
            return [A.ExprStmt(e, **self.pos(t))]
        raise self.unsupported("expression statement with no effect", t)

    def expr(self, level=1):
        left = self.unary()
        while True:
            t = self.peek()
            p = BINARY.get(t.text) if t.kind == "OP" else None
            if p is None or p < level:
                if t.kind == "OP" and t.text == "?":
                    return self.ternary(left, t, level)
                return left
            self.next()
            if t.text in ("|", "^", "&", "<<", ">>"):
                raise self.unsupported(f"bitwise operator '{t.text}'", t)
            if t.text == "**":
                left = A.Intrinsic("pow", [left, self.expr(p)], line=t.line, col=t.col)
                continue
            right = self.expr(p + 1)
            op = {"===": "==", "!==": "!="}.get(t.text, t.text)
            if op in ("||", "&&"):
                left = A.BoolOp(op, left, right, line=t.line, col=t.col)
            elif p in (6, 7):
                if isinstance(left, A.Compare):
                    raise self.unsupported("chained comparison", t)
                left = A.Compare(op, left, right, line=t.line, col=t.col)
            else:
                left = A.BinOp(op, left, right, line=t.line, col=t.col)

    def skip_braced(self):
        while not self.at_op("{"):
            if self.at("EOF"):
                raise self.error("expected '{'")
            self.next()
        depth = 0
        while True:
            tok = self.next()
            if tok.kind == "EOF":
                raise self.error("expected '}'")
            depth += {"{": 1, "}": -1}.get(tok.text, 0) if tok.kind == "PUNCT" else 0
            if depth == 0:
                return tok

    def ternary(self, cond, t, level):
        k = [self.peek(n) for n in (1, 2, 3)]
        texts = tuple(x.text[1:-1] for x in (k[0], k[2]))
        if level == 1 and k[0].kind == "STRING" and k[1].text == ":" and k[2].kind == "STRING" and texts in BOOL_TEXT:
            for _ in range(4):
                self.next()
            return A.Intrinsic(BOOL_TEXT[texts], [cond], line=t.line, col=t.col)
        raise self.unsupported("conditional expression '?:'", t)

    def unary(self):
        t = self.peek()
        if self.at_op("!"):
            self.next()
            return A.UnaryOp("!", self.unary(), line=t.line, col=t.col)
        if self.at_op("-"):
            self.next()
            e = self.unary()
            if isinstance(e, A.IntLit):
                return A.IntLit(-e.value, line=t.line, col=t.col)
            if isinstance(e, A.FloatLit):
                return A.FloatLit(-e.value, line=t.line, col=t.col)
            return A.UnaryOp("-", e, line=t.line, col=t.col)
        if self.at_op("+"):
            self.next()
            return self.unary()
        if self.at_op("~"):
            raise self.unsupported("bitwise operator '~'", t)
        if self.at_op("++", "--"):
            raise self.unsupported(f"'{t.text}' inside an expression", t)
        cast = self.cast()
        if cast is not None:
            return cast
        return self.postfix(self.primary())

    def cast(self):
        return None

    def postfix(self, e):
        while True:
            t = self.peek()
            if self.at_op("["):
                self.next()
                pos = {"line": e.line, "col": e.col}
                index = None if self.SLICE and self.at_op(self.SLICE) else self.expr()
                if self.SLICE and self.accept_op(self.SLICE):
                    stop = None if self.at_op("]") else self.expr()
                    self.expect_op("]")
                    e = A.Intrinsic("slice", [e, index or A.IntLit(0, **pos), stop or A.Len(e, **pos)], **pos)
                    continue
                self.expect_op("]")
                e = A.Index(e, index, **pos)
            elif self.at_op("."):
                self.next()
                name = self.next() if self.peek().kind == "KEYWORD" else self.expect("NAME", what="a member name")
                e = self.member(e, name, t)
            elif self.at_op("("):
                raise self.unsupported("calling an expression", t)
            elif self.at_op("->"):
                e = self.arrow(e, t)
            else:
                return e

    def member(self, e, name, t):
        raise self.unsupported(f"member '.{name.text}'", t)

    def arrow(self, e, t):
        raise self.unsupported("'->' member access", t)

    def args(self):
        self.expect_op("(")
        out = []
        while not self.at_op(")"):
            out.append(self.expr())
            if not self.accept_op(","):
                break
        self.expect_op(")")
        return out

    def number(self, t):
        raw = t.text.lower().replace("_", "")
        if not raw.startswith("0x") and ("." in raw or "e" in raw or raw.endswith(("f", "d"))):
            if raw.endswith(("f", "l")):
                raise self.unsupported("float or long double literal (use a plain double)", t)
            try:
                return A.FloatLit(float(raw.rstrip("d")), line=t.line, col=t.col)
            except ValueError:
                raise self.fail(f"Syntax error: invalid number '{t.text}'", t)
        text = raw.rstrip("l")
        if text.endswith("u"):
            raise self.unsupported("unsigned literal", t)
        try:
            v = int(text, 16) if text.startswith("0x") else int(text, 8) if len(text) > 1 and text.startswith("0") else int(text)
        except ValueError:
            raise self.fail(f"Syntax error: invalid number '{t.text}'", t)
        return A.IntLit(v, line=t.line, col=t.col)

    def string(self):
        t = self.peek()
        value = ""
        while self.at("STRING"):
            s = self.next()
            value += unescape(s.text[1:-1], s, self.fail)
        return A.StrLit(value, line=t.line, col=t.col)

    def char(self, t):
        value = unescape(t.text[1:-1], t, self.fail)
        if len(value) != 1:
            raise self.fail("Syntax error: character literal must hold one character", t)
        return A.CharLit(value, line=t.line, col=t.col)

    def primary(self):
        t = self.peek()
        if t.kind == "NUMBER":
            return self.number(self.next())
        if t.kind == "STRING":
            return self.string()
        if t.kind == "CHAR":
            return self.char(self.next())
        if t.kind == "KEYWORD" and t.text in ("true", "false"):
            self.next()
            return A.BoolLit(t.text == "true", line=t.line, col=t.col)
        if self.at_op("("):
            self.next()
            e = self.expr()
            self.expect_op(")")
            return e
        e = self.primary_extra()
        if e is not None:
            return e
        if t.kind in ("NAME", "BUILTIN"):
            self.next()
            if self.at_op("("):
                return self.call(t, self.args())
            if t.kind == "BUILTIN":
                raise self.unsupported(f"using '{t.text}' as a value", t)
            return A.Name(t.text, line=t.line, col=t.col)
        raise self.error("expected an expression")

    def primary_extra(self):
        return None

    def call(self, t, args):
        if t.kind == "BUILTIN":
            raise self.unsupported(f"library function {t.text}()", t)
        return A.Call(t.text, args, line=t.line, col=t.col)
