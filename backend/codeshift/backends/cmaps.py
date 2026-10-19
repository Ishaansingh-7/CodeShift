from .clists import ELEM, decl, ptr

KEYS = ["i64", "str"]
VALS = ["i64", "f64", "str", "bool"]
KIND = {"int": "i64", "float": "f64", "str": "str", "bool": "bool"}
ZERO = {"i64": "0", "f64": "0.0", "str": '""', "bool": "0"}
MOPS = ["new", "find", "put", "get_or", "get", "has", "del", "incr", "keys"]
SOPS = ["new", "find", "add", "has", "del", "items"]
LIST_OPS = {"keys": ["new", "push", "sort"], "items": ["new", "push"]}


def map_kind(t):
    k, v = t[4:-1].split(",")
    return f"{KIND[k]}_{KIND[v]}" if KIND.get(k) in KEYS and KIND.get(v) in VALS else None


def set_kind(t):
    k = KIND.get(t[4:-1])
    return k if k in KEYS else None


def split(name):
    if name.startswith("cs_map_"):
        kv = name[7:].split("_")
        return ("map", "type", kv[0], kv[1]) if len(kv) == 2 and kv[0] in KEYS and kv[1] in VALS else None
    if name.startswith("cs_set_"):
        return ("set", "type", name[7:], None) if name[7:] in KEYS else None
    for prefix, ops, kind in (("cs_m", MOPS, "map"), ("cs_s", SOPS, "set")):
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        for op in ops:
            if rest.startswith(op + "_"):
                kv = rest[len(op) + 1:].split("_")
                if kind == "map" and len(kv) == 2 and kv[0] in KEYS and kv[1] in VALS:
                    return "map", op, kv[0], kv[1]
                if kind == "set" and len(kv) == 1 and kv[0] in KEYS:
                    return "set", op, kv[0], None
    return None


def known(name):
    return split(name) is not None


def rank(name):
    kind, op, k, v = split(name)
    ops = ["type"] + (MOPS if kind == "map" else SOPS)
    order = KEYS.index(k) * len(VALS) + (VALS.index(v) if v else 0)
    return 2 + (kind == "set"), order, ops.index(op)


def helper(name):
    kind, op, k, v = split(name)
    return map_helper(op, k, v) if kind == "map" else set_helper(op, k)


def same(a, b, k):
    return f"strcmp({a}, {b}) == 0" if k == "str" else f"{a} == {b}"


def map_helper(op, k, v):
    kt, vt = ELEM[k], ELEM[v]
    m, kv = f"cs_map_{k}_{v}", f"{k}_{v}"
    heads = ["string.h"] if k == "str" else []
    if op == "type":
        return [], [], f"""typedef struct
{{
    {ptr(kt)}keys;
    {ptr(vt)}vals;
    int len;
    int cap;
}} {m};"""
    if op == "new":
        return ["stdlib.h"], [m], f"""static {m} *cs_mnew_{kv}(void)
{{
    {m} *m = malloc(sizeof({m}));
    m->len = 0;
    m->cap = 8;
    m->keys = malloc(8 * sizeof({kt}));
    m->vals = malloc(8 * sizeof({vt}));
    return m;
}}"""
    if op == "find":
        return heads, [m], f"""static int cs_mfind_{kv}({m} *m, {decl(kt, "k")})
{{
    for (int i = 0; i < m->len; i++)
    {{
        if ({same("m->keys[i]", "k", k)})
        {{
            return i;
        }}
    }}
    return -1;
}}"""
    if op == "put":
        return ["stdlib.h"], [f"cs_mfind_{kv}"], f"""static void cs_mput_{kv}({m} *m, {decl(kt, "k")}, {decl(vt, "v")})
{{
    int i = cs_mfind_{kv}(m, k);
    if (i < 0)
    {{
        if (m->len == m->cap)
        {{
            m->cap *= 2;
            m->keys = realloc(m->keys, m->cap * sizeof({kt}));
            m->vals = realloc(m->vals, m->cap * sizeof({vt}));
        }}
        i = m->len++;
        m->keys[i] = k;
    }}
    m->vals[i] = v;
}}"""
    if op in ("get", "get_or"):
        extra, miss = (f", {decl(vt, 'd')}", "d") if op == "get_or" else ("", ZERO[v])
        return [], [f"cs_mfind_{kv}"], f"""static {decl(vt, f"cs_m{op}_{kv}({m} *m, {decl(kt, 'k')}{extra})")}
{{
    int i = cs_mfind_{kv}(m, k);
    return i < 0 ? {miss} : m->vals[i];
}}"""
    if op == "has":
        return [], [f"cs_mfind_{kv}"], f"""static int cs_mhas_{kv}({m} *m, {decl(kt, "k")})
{{
    return cs_mfind_{kv}(m, k) >= 0;
}}"""
    if op == "del":
        return [], [f"cs_mfind_{kv}"], f"""static void cs_mdel_{kv}({m} *m, {decl(kt, "k")})
{{
    int i = cs_mfind_{kv}(m, k);
    if (i < 0)
    {{
        return;
    }}
    for (int j = i; j < m->len - 1; j++)
    {{
        m->keys[j] = m->keys[j + 1];
        m->vals[j] = m->vals[j + 1];
    }}
    m->len--;
}}"""
    if op == "incr":
        return [], [f"cs_mfind_{kv}", f"cs_mput_{kv}"], f"""static void cs_mincr_{kv}({m} *m, {decl(kt, "k")}, {decl(vt, "v")})
{{
    int i = cs_mfind_{kv}(m, k);
    if (i < 0)
    {{
        cs_mput_{kv}(m, k, v);
    }}
    else
    {{
        m->vals[i] += v;
    }}
}}"""
    if op == "keys":
        return [], [m, f"cs_new_{k}", f"cs_push_{k}", f"cs_sort_{k}"], f"""static cs_list_{k} *cs_mkeys_{kv}({m} *m)
{{
    cs_list_{k} *r = cs_new_{k}();
    for (int i = 0; i < m->len; i++)
    {{
        cs_push_{k}(r, m->keys[i]);
    }}
    cs_sort_{k}(r);
    return r;
}}"""
    raise KeyError(op)


def set_helper(op, k):
    t, s = ELEM[k], f"cs_set_{k}"
    heads = ["string.h"] if k == "str" else []
    eq = same("s->data[i]", "v", k)
    if op == "type":
        return [], [], f"""typedef struct
{{
    {ptr(t)}data;
    int len;
    int cap;
}} {s};"""
    if op == "new":
        return ["stdlib.h"], [s], f"""static {s} *cs_snew_{k}(void)
{{
    {s} *s = malloc(sizeof({s}));
    s->len = 0;
    s->cap = 8;
    s->data = malloc(8 * sizeof({t}));
    return s;
}}"""
    if op == "find":
        less = "strcmp(s->data[i], v) < 0" if k == "str" else "s->data[i] < v"
        return heads, [s], f"""static int cs_sfind_{k}({s} *s, {decl(t, "v")})
{{
    int i = 0;
    while (i < s->len && {less})
    {{
        i++;
    }}
    return i;
}}"""
    if op == "has":
        return heads, [f"cs_sfind_{k}"], f"""static int cs_shas_{k}({s} *s, {decl(t, "v")})
{{
    int i = cs_sfind_{k}(s, v);
    return i < s->len && {eq};
}}"""
    if op == "add":
        return ["stdlib.h", *heads], [f"cs_sfind_{k}"], f"""static void cs_sadd_{k}({s} *s, {decl(t, "v")})
{{
    int i = cs_sfind_{k}(s, v);
    if (i < s->len && {eq})
    {{
        return;
    }}
    if (s->len == s->cap)
    {{
        s->cap *= 2;
        s->data = realloc(s->data, s->cap * sizeof({t}));
    }}
    for (int j = s->len; j > i; j--)
    {{
        s->data[j] = s->data[j - 1];
    }}
    s->data[i] = v;
    s->len++;
}}"""
    if op == "del":
        return heads, [f"cs_sfind_{k}"], f"""static void cs_sdel_{k}({s} *s, {decl(t, "v")})
{{
    int i = cs_sfind_{k}(s, v);
    if (i >= s->len || !({eq}))
    {{
        return;
    }}
    for (int j = i; j < s->len - 1; j++)
    {{
        s->data[j] = s->data[j + 1];
    }}
    s->len--;
}}"""
    if op == "items":
        return [], [s, f"cs_new_{k}", f"cs_push_{k}"], f"""static cs_list_{k} *cs_sitems_{k}({s} *s)
{{
    cs_list_{k} *r = cs_new_{k}();
    for (int i = 0; i < s->len; i++)
    {{
        cs_push_{k}(r, s->data[i]);
    }}
    return r;
}}"""
    raise KeyError(op)
