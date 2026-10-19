import re
from dataclasses import dataclass

from ... import ast as A
from ...library import LISTOPS, MAP_GENERIC, MAPOPS
from ...semantic import mp, sset
from ...tokens import Token
from .. import idioms
from ..cfamily import ASSIGN, CFamily, unescape

INTS = {"i8", "i16", "i32", "i64", "i128", "isize", "u8", "u16", "u32", "u64", "u128", "usize"}
CASTS = {"i64", "isize", "usize", "u64", "char", "f64", "u8", "u32", "i32"}
HELPERS = {"cs_round_js": "round_js", "cs_bool_py": "b2s_py", "cs_sorted": "sorted", "cs_read_line": "read_line"}
SPEC = re.compile(r"([<>])?(\d+)?(?:\.(\d+))?$")
MAPS = {"BTreeMap", "HashMap"}
SETS = {"BTreeSet", "HashSet"}
METHODS = {
    "abs": "abs", "min": "min", "max": "max", "pow": "pow_i", "powf": "pow_f", "sqrt": "sqrt", "floor": "floor",
    "ceil": "ceil", "trunc": "trunc", "round": "round_away", "round_ties_even": "round_even", "sin": "sin",
    "cos": "cos", "tan": "tan", "atan2": "atan2", "ln": "log", "log10": "log10", "log2": "log2", "exp": "exp",
    "hypot": "hypot", "to_uppercase": "to_upper", "to_lowercase": "to_lower", "to_ascii_uppercase": "cupper",
    "to_ascii_lowercase": "clower", "starts_with": "starts", "ends_with": "ends", "contains": "contains",
    "replace": "replace_all", "repeat": "repeat", "is_ascii_digit": "is_digit", "is_ascii_alphabetic": "is_alpha",
    "is_ascii_whitespace": "is_space", "is_ascii_uppercase": "is_upper", "is_ascii_lowercase": "is_lower",
}
SUFFIXES = sorted(INTS, key=len, reverse=True)


@dataclass(eq=False)
class Tuple(A.Expr):
    items: list


@dataclass(eq=False)
class Log(A.Expr):
    args: list


@dataclass(eq=False)
class Method(A.Expr):
    obj: object
    name: str
    args: list


@dataclass(eq=False)
class Entry(A.Expr):
    obj: object
    key: list
    default: list


@dataclass(eq=False)
class Tail(A.Stmt):
    value: object


def parse(tokens):
    return RustParser(tokens).module()


class RustParser(CFamily):
    lang = "rust"
    SLICE = ".."

    def module(self):
        funcs, main, helpers, uses = [], None, [], []
        while not self.at("EOF"):
            t = self.peek()
            if t.kind == "KEYWORD" and t.text == "use":
                self.next()
                path = []
                while not self.at_op(";"):
                    if self.at("EOF"):
                        raise self.error("expected ';'")
                    path.append(self.next().text)
                end = self.expect_op(";")
                text = "".join(path)
                names = text.removeprefix("std::collections::").strip("{}").split(",")
                if not text.startswith("std::collections::") or not set(names) <= MAPS | SETS:
                    raise self.unsupported(f"use {text}", t)
                uses.append((t.line, end.line))
                continue
            self.accept("KEYWORD", "pub")
            if not self.at("KEYWORD", "fn"):
                raise self.unsupported(f"top-level '{t.text}' (only functions)", t)
            if self.peek(1).text in HELPERS:
                self.next()
                name = self.next()
                helpers.append(({HELPERS[name.text]}, t.line, self.skip_braced().line))
                continue
            fn = self.function()
            if fn.name == "main":
                main = fn
            else:
                funcs.append(fn)
        if main is None:
            raise self.unsupported("a program without fn main", self.peek())
        wrap = [(main.line, main.end), *uses]
        m = A.Module(funcs, main.body, entry=(main.line, main.end), lang="rust", wrap=wrap, line=1, col=1)
        idioms.attach(m, helpers)
        return m

    def function(self):
        t = self.next()
        name = self.expect("NAME", what="a function name")
        if self.at_op("<"):
            raise self.unsupported("generic functions", self.peek())
        self.expect_op("(")
        params = []
        self.scopes = [set()]
        while not self.at_op(")"):
            self.accept("KEYWORD", "mut")
            p = self.expect("NAME", what="a parameter name")
            self.expect_op(":")
            params.append(A.Param(p.text, self.rtype(), line=p.line, col=p.col))
            self.scopes[0].add(p.text)
            if not self.accept_op(","):
                break
        self.expect_op(")")
        ret = self.rtype() if self.accept_op("->") else "void"
        if name.text == "main" and (params or ret != "void"):
            raise self.unsupported("main with parameters or a result", name)
        body = self.block()
        self.settle(body, ret != "void")
        self.loop_names(body, {p.name for p in params})
        for n in A.walk_all(body):
            if isinstance(n, Method):
                raise self.unsupported(f"method '.{n.name}()' here", n)
            if isinstance(n, Entry):
                raise self.unsupported("entry() used this way (only *m.entry(k).or_insert(0) += v)", n)
            if isinstance(n, (Tuple, Log)):
                raise self.unsupported("a tuple value here" if isinstance(n, Tuple) else "println! inside an expression", n)
        return A.FunctionDef(name.text, params, body, ret, **self.pos(t))

    def rtype(self):
        t = self.peek()
        if self.accept_op("&", "&&"):
            self.accept("KEYWORD", "mut")
            if self.at_op("["):
                return self.slice()
            inner = self.rtype()
            if inner != "str" and not inner.startswith(("arr", "list<", "map<", "set<")):
                raise self.unsupported("references to this type", t)
            return inner
        if self.at_op("["):
            return self.slice()
        if self.at_op("("):
            raise self.unsupported("tuple types", t)
        tt = self.expect("TYPE", what="a type")
        if tt.text == "f32":
            raise self.unsupported("f32 (use f64)", tt)
        if tt.text == "f64":
            return "float"
        if tt.text in INTS:
            return "int"
        if tt.text in ("bool", "char"):
            return tt.text
        if tt.text in ("str", "String"):
            return "str"
        if tt.text == "Vec":
            self.expect_op("<")
            el = self.rtype()
            self.close_angle()
            return self.list_of(el, tt)
        if tt.text in MAPS or tt.text in SETS:
            self.expect_op("<")
            k = self.rtype()
            v = None
            if tt.text in MAPS:
                self.expect_op(",")
                v = self.rtype()
            self.close_angle()
            return mp(k, v) if tt.text in MAPS else sset(k)
        raise self.unsupported(f"type {tt.text}", tt)

    def list_of(self, el, t):
        if el == "char":
            raise self.unsupported("vectors of characters", t)
        return "arr" if el == "int" else f"list<{el}>"

    def close_angle(self):
        tok = self.peek()
        if tok.text == ">>":
            self.toks[self.i] = Token("OP", ">", tok.line, tok.col + 1)
            return
        self.expect_op(">")

    def slice(self):
        t = self.expect_op("[")
        el = self.rtype()
        if self.at_op(";"):
            raise self.unsupported("fixed-size arrays (use a slice or Vec)", t)
        self.expect_op("]")
        return self.list_of(el, t)

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

    def bind(self, tok):
        if any(tok.text in s for s in self.scopes[:-1][len(self.scopes) == 2:]):
            raise self.unsupported(f"redeclaring '{tok.text}' inside an inner block (shadowing)", tok)
        self.scopes[-1].add(tok.text)

    def statement(self):
        t = self.peek()
        if self.at_op("{"):
            return self.block()
        if self.accept_op(";"):
            return []
        if t.kind == "KEYWORD":
            if t.text == "let":
                return self.let()
            if t.text == "if":
                return [self.if_stmt()]
            if t.text == "while":
                return [self.while_stmt()]
            if t.text == "loop":
                self.next()
                return [A.While(A.BoolLit(True, line=t.line, col=t.col), self.block(), **self.pos(t))]
            if t.text == "for":
                return self.for_stmt()
            if t.text == "return":
                return [self.return_stmt()]
            if t.text == "fn":
                raise self.unsupported("nested functions", t)
            if t.text in ("break", "continue"):
                self.next()
                if not self.at_op(";", "}"):
                    raise self.unsupported(f"'{t.text}' with a value or label", t)
                if not self.at_op("}"):
                    self.end()
                return [(A.Break if t.text == "break" else A.Continue)(**self.pos(t))]
            if t.text not in ("true", "false", "self"):
                raise self.unsupported(f"'{t.text}' statement", t)
        lhs = self.expr()
        if self.at_op(*ASSIGN):
            op = self.next()
            value = self.expr()
            if not self.at_op("}"):
                self.end()
            return [self.assignment(lhs, op, value, t)]
        if self.at_op("}"):
            return [Tail(lhs, **self.pos(t))]
        self.end()
        return self.expr_statement(lhs, t)

    def let(self):
        t = self.next()
        if self.accept_op("("):
            pats = []
            while not self.at_op(")"):
                self.accept("KEYWORD", "mut")
                pats.append(self.expect("NAME", what="a variable name"))
                if not self.accept_op(","):
                    break
            self.expect_op(")")
            self.expect_op("=")
            values = self.expr()
            if not isinstance(values, Tuple) or len(values.items) != len(pats):
                raise self.unsupported("this destructuring let", t)
            values = values.items
            types = [None] * len(pats)
        else:
            self.accept("KEYWORD", "mut")
            pats = [self.expect("NAME", what="a variable name")]
            types = [self.rtype() if self.accept_op(":") else None]
            values = [self.expr()] if self.accept_op("=") else [None]
        self.end()
        for p in pats:
            if p.text == "_":
                raise self.unsupported("let _ (discarded values)", p)
            self.bind(p)
        if values[0] is None:
            return []
        names = [A.Name(p.text, line=p.line, col=p.col) for p in pats]
        return idioms.declare(names, values, types, self.pos(t))

    def if_stmt(self):
        t = self.next()
        test = self.expr()
        body = self.block()
        orelse = []
        if self.accept("KEYWORD", "else"):
            orelse = [self.if_stmt()] if self.at("KEYWORD", "if") else self.block()
        return A.If(test, body, orelse, **self.pos(t))

    def while_stmt(self):
        t = self.next()
        if self.at("KEYWORD", "let"):
            raise self.unsupported("while let", t)
        test = self.expr()
        return A.While(test, self.block(), **self.pos(t))

    def return_stmt(self):
        t = self.next()
        value = None if self.at_op(";", "}") else self.expr()
        if not self.at_op("}"):
            self.end()
        return A.Return(value, **self.pos(t))

    def for_stmt(self):
        t = self.next()
        borrow = bool(self.accept_op("&"))
        if self.at_op("("):
            raise self.unsupported("tuple patterns in for loops", t)
        var = self.expect("NAME", what="a loop variable")
        self.expect("KEYWORD", "in", "'in'")
        rng = self.range_iter()
        self.scopes.append({var.text})
        body = self.block()
        self.scopes.pop()
        at = self.pos(t)
        if isinstance(rng, tuple):
            start, stop, step = rng
            if borrow:
                raise self.unsupported("'&' pattern on a range", t)
            return [A.For(var.text, "range", body, start=start, stop=stop, step=step, **at)]
        return [A.For(var.text, "each", body, iter=rng, **at)]

    def range_iter(self):
        t = self.peek()
        paren = False
        if self.at_op("("):
            save = self.i, self.last
            self.next()
            lo = self.expr()
            if self.at_op("..", "..="):
                paren = True
            else:
                self.i, self.last = save
        if not paren:
            lo = self.expr()
            if not self.at_op("..", "..="):
                return self.iterable(lo, t)
        op = self.next()
        hi = self.expr()
        if op.text == "..=":
            hi = self.plus(hi, 1)
        one = A.IntLit(1, line=t.line, col=t.col)
        start, stop, step = lo, hi, one
        if paren:
            self.expect_op(")")
            rev = False
            while self.accept_op("."):
                m = self.expect("NAME", what="a method name")
                args = self.args()
                if m.text == "rev" and not args and not rev and step.value == 1:
                    rev = True
                    start, stop, step = self.plus(hi, -1), self.plus(lo, -1), A.IntLit(-1, line=t.line, col=t.col)
                elif m.text == "step_by" and len(args) == 1 and isinstance(args[0], A.IntLit) and args[0].value > 0 \
                        and abs(step.value) == 1:
                    step = A.IntLit(args[0].value * step.value, line=t.line, col=t.col)
                else:
                    raise self.unsupported(f"range method '.{m.text}()'", m)
        return start, stop, step

    def plus(self, e, k):
        if isinstance(e, A.IntLit):
            return A.IntLit(e.value + k, line=e.line, col=e.col)
        if isinstance(e, A.BinOp) and e.op in "+-" and isinstance(e.right, A.IntLit):
            v = e.right.value * (1 if e.op == "+" else -1) + k
            if v == 0:
                return e.left
            return A.BinOp("+" if v > 0 else "-", e.left, A.IntLit(abs(v), line=e.line, col=e.col), line=e.line, col=e.col)
        return A.BinOp("+" if k > 0 else "-", e, A.IntLit(abs(k), line=e.line, col=e.col), line=e.line, col=e.col)

    def iterable(self, e, t):
        if isinstance(e, Method) and e.name in ("keys", "keys_cloned") and not e.args:
            return A.Intrinsic("sorted", [e.obj], line=e.line, col=e.col)
        if isinstance(e, Method) and e.name in ("chars", "iter", "iter_cloned") and not e.args:
            return e.obj
        if isinstance(e, (A.Name, A.ArrayLit)):
            return e
        raise self.unsupported("looping over this expression", t)

    def unary(self):
        t = self.peek()
        if self.accept_op("&", "&&"):
            self.accept("KEYWORD", "mut")
            e = self.unary()
        elif self.accept_op("*"):
            e = self.unary()
        else:
            e = super().unary()
        while self.at("KEYWORD", "as"):
            self.next()
            ty = self.expect("TYPE", what="a type")
            if ty.text not in CASTS:
                raise self.unsupported(f"casting to {ty.text}", ty)
            kind = {"f64": "num_float", "char": "num_char"}.get(ty.text, "num_int")
            e = A.Intrinsic(kind, [e], line=e.line, col=e.col)
        return e

    def number(self, t):
        text = t.text.replace("_", "")
        for s in SUFFIXES:
            if text.endswith(s) and text[:-len(s)].isdigit():
                text = text[:-len(s)]
                break
        if not text.isdigit() and not text.lower().startswith(("0x", "0o", "0b")):
            if text.endswith("f32"):
                raise self.unsupported("f32 literal (use f64)", t)
            try:
                return A.FloatLit(float(text.removesuffix("f64")), line=t.line, col=t.col)
            except ValueError:
                raise self.fail(f"Syntax error: invalid number '{t.text}'", t)
        base = {"0x": 16, "0o": 8, "0b": 2}.get(text[:2].lower(), 10)
        try:
            return A.IntLit(int(text, base), line=t.line, col=t.col)
        except ValueError:
            raise self.fail(f"Syntax error: invalid number '{t.text}'", t)

    def primary(self):
        t = self.peek()
        if self.at_op("("):
            self.next()
            if self.at_op(")"):
                raise self.unsupported("the unit value ()", t)
            items = [self.expr()]
            while self.accept_op(","):
                if self.at_op(")"):
                    break
                items.append(self.expr())
            self.expect_op(")")
            return items[0] if len(items) == 1 else Tuple(items, line=t.line, col=t.col)
        return super().primary()

    def primary_extra(self):
        t = self.peek()
        if self.at_op("["):
            return self.list_items(self.next())
        if t.kind == "KEYWORD" and t.text in ("if", "match", "loop", "self", "move"):
            raise self.unsupported(f"'{t.text}' used as a value", t)
        if t.kind == "TYPE" and t.text == "String" and self.peek(1).text == "::":
            self.next()
            self.next()
            m = self.expect("NAME", what="a function name")
            args = self.args()
            if m.text == "new" and not args:
                return A.StrLit("", line=t.line, col=t.col)
            if m.text == "from" and len(args) == 1:
                return args[0]
            raise self.unsupported(f"String::{m.text}", m)
        if t.kind == "TYPE" and t.text in MAPS | SETS and self.peek(1).text == "::" and self.peek(2).text == "new":
            for _ in range(3):
                self.next()
            self.expect_op("(")
            self.expect_op(")")
            return A.Intrinsic("map_new" if t.text in MAPS else "set_new", [], line=t.line, col=t.col)
        if t.kind == "TYPE" and t.text == "Vec" and self.peek(1).text == "::" and self.peek(2).text == "new":
            for _ in range(3):
                self.next()
            self.expect_op("(")
            self.expect_op(")")
            return A.ArrayLit([], line=t.line, col=t.col)
        if t.kind in ("NAME", "TYPE") and self.peek(1).text == "::":
            parts = [self.next().text]
            while self.accept_op("::"):
                parts.append(self.next().text)
            path = "::".join(parts)
            if path == "std::process::exit" and self.at_op("("):
                args = self.args()
                if len(args) != 1:
                    raise self.fail("Syntax error: exit takes one argument", t)
                return A.Intrinsic("exit", args, line=t.line, col=t.col)
            if path in ("std::f64::consts::PI", "std::f64::consts::E"):
                return A.Intrinsic("pi" if path.endswith("PI") else "e", [], line=t.line, col=t.col)
            raise self.unsupported(f"path '{path}'", t)
        if t.kind == "NAME" and self.peek(1).text == "!" and self.peek(2).text in ("(", "["):
            return self.macro()
        return None

    def list_items(self, open_tok):
        items = []
        while not self.at_op("]"):
            items.append(self.expr())
            if self.accept_op(";"):
                count = self.expr()
                self.expect_op("]")
                pos = {"line": open_tok.line, "col": open_tok.col}
                v = items[0]
                if isinstance(v, A.Intrinsic) and v.name == "list_fill" and len(items) == 1:
                    return A.Intrinsic("grid", [count, v.args[1], v.args[0]], **pos)
                return A.Intrinsic("list_fill", [v, count], **pos)
            if not self.accept_op(","):
                break
        self.expect_op("]")
        return A.ArrayLit(items, line=open_tok.line, col=open_tok.col)

    def macro(self):
        t = self.next()
        self.next()
        if t.text == "vec":
            if not self.at_op("["):
                raise self.unsupported("vec! with parentheses", t)
            return self.list_items(self.next())
        if t.text not in ("println", "format", "print"):
            raise self.unsupported(f"macro {t.text}!", t)
        self.expect_op("(")
        if self.at_op(")"):
            self.next()
            if t.text != "println":
                raise self.fail(f"Syntax error: {t.text}! needs a format string", t)
            return Log([], line=t.line, col=t.col)
        f = self.expect("STRING", what="a format string")
        args = []
        while self.accept_op(","):
            if self.at_op(")"):
                break
            args.append(self.expr())
        self.expect_op(")")
        items = self.placeholders(unescape(f.text[1:-1], f, self.fail), args, f)
        if t.text == "format":
            if not items:
                return A.StrLit("", line=t.line, col=t.col)
            e = items[0]
            for x in items[1:]:
                e = A.BinOp("+", e, x, line=t.line, col=t.col)
            return e
        node = Log(self.split(items, f), line=t.line, col=t.col)
        if t.text == "print":
            node.ending = ""
            if len(items) == 1 and isinstance(items[0], A.StrLit) and not items[0].value.strip(" "):
                node.args, node.ending = [], items[0].value
        return node

    def placeholders(self, text, args, f):
        items, buf, k, i = [], "", 0, 0
        while i < len(text):
            c = text[i]
            if text.startswith("{{", i) or text.startswith("}}", i):
                buf += c
                i += 2
                continue
            if c == "}":
                raise self.fail("Syntax error: unmatched '}' in format string", f)
            if c != "{":
                buf += c
                i += 1
                continue
            end = text.find("}", i)
            if end < 0:
                raise self.fail("Syntax error: unmatched '{' in format string", f)
            spec = text[i + 1:end]
            name, _, fmt = spec.partition(":")
            m = SPEC.match(fmt) if fmt not in ("", "?") else None
            if fmt not in ("", "?") and (not m or not (m.group(2) or m.group(3))):
                raise self.unsupported(f"format spec '{{{spec}}}'", f)
            if buf:
                items.append(A.StrLit(buf, line=f.line, col=f.col))
                buf = ""
            if name:
                if not name.isidentifier():
                    raise self.unsupported(f"format argument '{{{spec}}}'", f)
                items.append(A.Name(name, line=f.line, col=f.col))
            else:
                if k >= len(args):
                    raise self.fail("Syntax error: more {} placeholders than arguments", f)
                items.append(args[k])
                k += 1
            if m:
                pos = {"line": f.line, "col": f.col}
                align, width, prec = m.groups()
                v = items[-1]
                if prec:
                    v = A.Intrinsic("fixed", [v, A.IntLit(int(prec), **pos)], **pos)
                if width:
                    w = A.IntLit(int(width), **pos)
                    if align or prec:
                        inner = v if prec else A.Intrinsic("str", [v], **pos)
                        v = A.Intrinsic("ljust" if align == "<" else "rjust", [inner, w], **pos)
                    else:
                        v = A.Intrinsic("pad", [v, w], **pos)
                items[-1] = v
            i = end + 1
        if buf:
            items.append(A.StrLit(buf, line=f.line, col=f.col))
        if k != len(args):
            raise self.fail("Syntax error: more arguments than {} placeholders", f)
        return items

    def split(self, items, f):
        mark = chr(0)
        text, exprs = "", []
        for s in items:
            if isinstance(s, A.StrLit):
                text += s.value
            else:
                text += f"{mark}{len(exprs)}{mark}"
                exprs.append(s)
        return idioms.words(text, mark, exprs, {"line": f.line, "col": f.col})

    def seq(self, *texts):
        for want in texts:
            tok = self.peek()
            if want == ">" and tok.text == ">>":
                self.close_angle()
                continue
            if tok.text != want:
                raise self.unsupported(f"this method chain (expected '{want}')", tok)
            self.next()

    def closure_value(self, *head):
        self.seq("(", *head)
        v = self.expr()
        self.seq(")")
        return v

    def member(self, e, name, t):
        n = name.text
        pos = {"line": e.line, "col": e.col}
        if n == "get" and self.at_op("("):
            args = self.args()
            if len(args) == 1 and self.at_op(".") and self.peek(1).text in ("copied", "cloned"):
                self.seq(".", self.peek(1).text, "(", ")")
            if len(args) != 1 or not (self.at_op(".") and self.peek(1).text == "unwrap_or"):
                raise self.unsupported("get() without unwrap_or()", t)
            self.seq(".", "unwrap_or")
            d = self.args()
            return A.Intrinsic("map_get_or", [e, args[0], *d], **pos)
        if n == "entry" and self.at_op("("):
            args = self.args()
            self.seq(".", "or_insert")
            d = self.args()
            return Entry(e, args, d, **pos)
        if n == "keys" and self.at_op("("):
            self.seq("(", ")")
            return Method(e, "keys", [], **pos)
        if isinstance(e, Method) and e.name == "keys" and n == "cloned":
            self.seq("(", ")")
            return Method(e.obj, "keys_cloned", [], **pos)
        if isinstance(e, Method) and e.name in ("keys_cloned", "iter_cloned") and n == "collect":
            self.seq("::", "<")
            self.rtype()
            self.seq(">", "(", ")")
            return A.Intrinsic("collect", [e.obj], **pos)
        if n == "contains_key" and self.at_op("("):
            return A.Intrinsic("map_has", [e, *self.args()], **pos)
        it = isinstance(e, Method) and e.name in ("iter", "iter_cloned")
        if it and n == "position":
            v = self.closure_value("|", "e", "|", "*", "e", "==")
            self.seq(".", "map", "(", "|", "i", "|", "i", "as", "i64", ")", ".", "unwrap_or", "(", "-", "1", ")")
            return A.Intrinsic("index_of", [e.obj, v], **pos)
        if it and n == "any":
            v = self.closure_value("|", "e", "|", "e", "==")
            return A.Intrinsic("contains", [e.obj, v], **pos)
        if it and n == "sum":
            self.seq("::", "<")
            self.rtype()
            self.seq(">", "(", ")")
            return A.Intrinsic("sum", [e.obj], **pos)
        if it and n in ("min", "max"):
            self.seq("(", ")", ".", "unwrap", "(", ")")
            if self.at_op(".") and self.peek(1).text == "clone":
                self.seq(".", "clone", "(", ")")
            return A.Intrinsic("l" + n, [e.obj], **pos)
        if it and e.name == "iter" and n == "cloned" and self.at_op("("):
            self.seq("(", ")")
            if self.at_op(".") and self.peek(1).text == "fold":
                self.seq(".", "fold", "(", "f64", "::")
                start = self.next().text
                self.seq(",", "f64", "::")
                fn = self.next().text
                self.seq(")")
                if (start, fn) not in (("INFINITY", "min"), ("NEG_INFINITY", "max")):
                    raise self.unsupported("this fold()", t)
                return A.Intrinsic("l" + fn, [e.obj], **pos)
            return Method(e.obj, "iter_cloned", [], **pos)
        if n == "sort_by":
            self.seq("(", "|", "a", ",", "b", "|")
            first = self.next().text
            method = self.next() if self.accept_op(".") else None
            if method is None or method.text not in ("cmp", "partial_cmp"):
                raise self.unsupported("this sort_by() comparator", t)
            self.seq("(")
            second = self.next().text
            self.seq(")")
            if method.text == "partial_cmp":
                self.seq(".", "unwrap", "(", ")")
            self.seq(")")
            return A.Intrinsic("sort" if (first, second) == ("a", "b") else "sort_desc", [e], **pos)
        if n == "split_whitespace" and self.at_op("(") and self.peek(3).text == "map" and self.peek(5).text == "|":
            self.seq("(", ")", ".", "map", "(", "|")
            v = self.next().text
            self.seq("|", v, ".", "parse", "::", "<", "i64", ">", "(", ")", ".", "unwrap", "(", ")", ")", ".", "collect",
                     "::", "<", "Vec", "<", "i64", ">", ">", "(", ")")
            return A.Intrinsic("s2ints", [e], **pos)
        if n in ("split", "split_whitespace"):
            args = self.args()
            self.seq(".", "map", "(", "String", "::", "from", ")", ".", "collect", "::", "<", "Vec", "<", "String",
                     ">", ">", "(", ")")
            kind = "split" if n == "split" else "split_ws"
            return A.Intrinsic(kind, [e, *args], **pos)
        args = self.args() if self.at_op("(") else None
        if args is None:
            raise self.unsupported(f"field '.{n}'", t)
        if n == "len" and not args:
            return A.Len(e, line=e.line, col=e.col)
        if n == "to_string" and not args:
            return A.Intrinsic("str", [e], line=e.line, col=e.col)
        if n in ("clone", "to_owned") and not args:
            return e
        if n in METHODS:
            return A.Intrinsic(METHODS[n], [e, *args], line=e.line, col=e.col)
        if n == "find" and len(args) == 1:
            for want in (".", "map", "(", "|", "i", "|", "i", "as", "i64", ")", ".", "unwrap_or", "(", "-", "1", ")"):
                tok = self.next()
                if tok.text != want:
                    raise self.unsupported("find() without .map(|i| i as i64).unwrap_or(-1)", tok)
            return A.Intrinsic("find", [e, *args], line=e.line, col=e.col)
        if n == "trim" and not args and not (self.at_op(".") and self.peek(1).text == "parse"):
            return A.Intrinsic("trim", [e], line=e.line, col=e.col)
        if n == "trim" and not args and self.at_op(".") and self.peek(1).text == "parse":
            self.next()
            self.next()
            self.expect_op("::")
            self.expect_op("<")
            ty = self.expect("TYPE", what="a number type")
            self.expect_op(">")
            self.expect_op("(")
            self.expect_op(")")
            self.expect_op(".")
            if self.expect("NAME", what="unwrap").text != "unwrap":
                raise self.unsupported("parse() without unwrap()", t)
            self.expect_op("(")
            self.expect_op(")")
            if ty.text not in ("i64", "f64"):
                raise self.unsupported(f"parsing to {ty.text}", ty)
            return A.Intrinsic("s2i" if ty.text == "i64" else "s2f", [e], line=e.line, col=e.col)
        if n == "as_bytes" and not args:
            if not self.at_op("["):
                raise self.unsupported("as_bytes() without an index", t)
            self.next()
            i = self.expr()
            self.expect_op("]")
            return A.Index(e, i, line=e.line, col=e.col)
        if n == "insert" and len(args) == 1:
            return A.Intrinsic("set_add", [e, *args], **pos)
        if n in ("push", "insert", "reverse", "sort") and n != "insert" or n == "insert" and len(args) == 2:
            return A.Intrinsic(n, [e, *args], **pos)
        if n == "pop" and not args:
            self.seq(".", "unwrap", "(", ")")
            return A.Intrinsic("pop", [e], **pos)
        if n == "remove" and len(args) == 1:
            return A.Intrinsic("pop_at", [e, *args], **pos)
        if n == "to_vec" and not args:
            return e if isinstance(e, A.Intrinsic) and e.name == "slice" else A.Intrinsic("lcopy", [e], **pos)
        if n == "join" and len(args) == 1:
            return A.Intrinsic("join", [args[0], e], **pos)
        if n in ("chars", "iter", "swap", "push_str"):
            return Method(e, n, args, line=e.line, col=e.col)
        raise self.unsupported(f"method '.{n}()'", t)

    def call(self, t, args):
        if t.text in HELPERS:
            return A.Intrinsic(HELPERS[t.text], args, line=t.line, col=t.col)
        return A.Call(t.text, args, line=t.line, col=t.col)

    def assignment(self, lhs, op, value, t):
        if isinstance(lhs, Entry):
            zero = lhs.default[0] if len(lhs.default) == 1 else None
            if op.text not in ("+=", "-=") or len(lhs.key) != 1 or not isinstance(zero, (A.IntLit, A.FloatLit)) \
                    or zero.value != 0:
                raise self.unsupported("entry() used this way (only *m.entry(k).or_insert(0) += v)", t)
            if op.text == "-=":
                value = A.UnaryOp("-", value, line=value.line, col=value.col)
            node = A.Intrinsic("map_incr", [lhs.obj, lhs.key[0], value], line=lhs.line, col=lhs.col)
            return A.ExprStmt(node, **self.pos(t))
        if isinstance(lhs, Tuple):
            if op.text != "=" or not isinstance(value, Tuple) or len(lhs.items) != len(value.items):
                raise self.unsupported("this destructuring assignment", t)
            return idioms.assign([self.target(x) for x in lhs.items], value.items, self.pos(t))
        return super().assignment(lhs, op, value, t)

    def expr_statement(self, e, t):
        if isinstance(e, Log):
            node = A.Print(e.args, **self.pos(t))
            if hasattr(e, "ending"):
                node.ending = e.ending
            return [node]
        if isinstance(e, Method) and isinstance(e.obj, A.Name):
            obj, args, at = e.obj, e.args, self.pos(t)
            me = A.Name(obj.id, line=e.line, col=e.col)
            if e.name == "swap" and len(args) == 2:
                return [A.Swap(A.Index(obj, args[0], line=e.line, col=e.col),
                               A.Index(A.Name(obj.id, line=e.line, col=e.col), args[1], line=e.line, col=e.col), **at)]
            if e.name == "push_str" and len(args) == 1:
                return [A.AugAssign(obj, "+", args[0], **at)]
            raise self.unsupported(f"method '.{e.name}()' here", t)
        if isinstance(e, Method):
            raise self.unsupported(f"method '.{e.name}()' here", t)
        if isinstance(e, A.Intrinsic) and e.name == "pop_at":
            e = A.Intrinsic("remove_at", e.args, line=e.line, col=e.col)
        if isinstance(e, A.Intrinsic) and (e.name in set(LISTOPS) or e.name in MAPOPS or e.name in MAP_GENERIC
                                           or e.name == "exit"):
            return [A.ExprStmt(e, **self.pos(t))]
        return super().expr_statement(e, t)

    def settle(self, stmts, value):
        k = 0
        while k < len(stmts):
            s = stmts[k]
            last = k == len(stmts) - 1
            if isinstance(s, Tail):
                if last and value:
                    stmts[k] = A.Return(s.value, line=s.line, col=s.col, end=s.end)
                else:
                    tok = type("T", (), {"line": s.line, "col": s.col})()
                    self.last = tok
                    if isinstance(s.value, (Log, Method, A.Call)):
                        stmts[k:k + 1] = self.expr_statement(s.value, tok)
                    else:
                        raise self.fail("Unsupported: a block that ends in a value here", tok)
                    for x in stmts[k:k + 1]:
                        x.end = s.end
            elif isinstance(s, A.If):
                self.settle(s.body, value and last)
                self.settle(s.orelse, value and last)
            else:
                for b in A.blocks(s):
                    self.settle(b, False)
            k += 1

    def loop_names(self, body, taken):
        used = set(taken)
        for n in A.walk_all(body):
            if isinstance(n, A.Name):
                used.add(n.id)
            elif isinstance(n, A.For):
                used.add(n.var)
        for n in A.walk_all(body):
            if isinstance(n, A.For) and n.var == "_":
                n.var = next(c for c in [*"ijk", *(f"i{k}" for k in range(2, 99))] if c not in used)
                used.add(n.var)
