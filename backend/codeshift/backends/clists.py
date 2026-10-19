from ..semantic import ARR

KINDS = ["i64", "f64", "str", "bool", "grid"]
ELEM = {"i64": "long long", "f64": "double", "str": "const char *", "bool": "int", "grid": "cs_list_i64 *"}
KIND = {ARR: "i64", "list<float>": "f64", "list<str>": "str", "list<bool>": "bool", "list<arr>": "grid"}
OPS = ["list", "new", "push", "from", "pop", "pop_at", "insert", "index_of", "contains", "cmp", "sort", "reverse",
       "sort_desc", "slice", "sorted", "sum", "min", "max", "fill", "show"]
ONLY = {"sum": {"i64", "f64"}, "min": {"i64", "f64", "str"}, "max": {"i64", "f64", "str"},
        "index_of": {"i64", "f64", "str", "bool"}, "contains": {"i64", "f64", "str", "bool"},
        "cmp": {"i64", "f64", "str", "bool"}, "sort": {"i64", "f64", "str", "bool"},
        "sort_desc": {"i64", "f64", "str", "bool"}, "sorted": {"i64", "f64", "str", "bool"}}
ITEM = {"i64": "cs_i2s(xs->data[i])", "f64": "cs_f2s(xs->data[i])", "str": "xs->data[i]",
        "bool": 'xs->data[i] ? "true" : "false"', "grid": "cs_show_i64(xs->data[i])"}
SHOWS = {"i64": ["cs_i2s"], "f64": ["cs_f2s"], "grid": ["cs_show_i64"]}
SOLO = {
    "cs_s2ints": (["stdlib.h"], ["cs_new_i64", "cs_push_i64"], """static cs_list_i64 *cs_s2ints(const char *s)
{
    cs_list_i64 *xs = cs_new_i64();
    char *end;
    long long v = strtoll(s, &end, 10);
    while (end != s)
    {
        cs_push_i64(xs, v);
        s = end;
        v = strtoll(s, &end, 10);
    }
    return xs;
}"""),
    "cs_grid": (["stdlib.h"], ["cs_new_grid", "cs_push_grid", "cs_fill_i64"], """static cs_list_grid *cs_grid(long long r, long long c, long long v)
{
    cs_list_grid *g = cs_new_grid();
    for (long long i = 0; i < r; i++)
    {
        cs_push_grid(g, cs_fill_i64(c, v));
    }
    return g;
}"""),
    "cs_split": (["stdlib.h", "string.h"], ["cs_new_str", "cs_push_str"], """static cs_list_str *cs_split(const char *s, const char *sep)
{
    cs_list_str *xs = cs_new_str();
    int n = strlen(sep);
    const char *p = s;
    const char *q;
    while ((q = strstr(p, sep)) != NULL)
    {
        char *w = malloc(q - p + 1);
        memcpy(w, p, q - p);
        w[q - p] = '\\0';
        cs_push_str(xs, w);
        p = q + n;
    }
    cs_push_str(xs, p);
    return xs;
}"""),
    "cs_split_ws": (["stdlib.h", "string.h", "ctype.h"], ["cs_new_str", "cs_push_str"], """static cs_list_str *cs_split_ws(const char *s)
{
    cs_list_str *xs = cs_new_str();
    int i = 0;
    while (s[i] != '\\0')
    {
        while (s[i] != '\\0' && isspace((unsigned char)s[i]))
        {
            i++;
        }
        int start = i;
        while (s[i] != '\\0' && !isspace((unsigned char)s[i]))
        {
            i++;
        }
        if (i > start)
        {
            char *w = malloc(i - start + 1);
            memcpy(w, s + start, i - start);
            w[i - start] = '\\0';
            cs_push_str(xs, w);
        }
    }
    return xs;
}"""),
    "cs_join": (["stdlib.h", "string.h"], ["cs_list_str"], """static const char *cs_join(const char *sep, cs_list_str *xs)
{
    int n = 1;
    for (int i = 0; i < xs->len; i++)
    {
        n += strlen(xs->data[i]) + strlen(sep);
    }
    char *s = malloc(n);
    s[0] = '\\0';
    for (int i = 0; i < xs->len; i++)
    {
        if (i > 0)
        {
            strcat(s, sep);
        }
        strcat(s, xs->data[i]);
    }
    return s;
}"""),
}


def decl(t, name):
    return t + name if t.endswith("*") else f"{t} {name}"


def ptr(t):
    return t + "*" if t.endswith("*") else t + " *"


def split(name):
    if name in SOLO:
        return None
    if name.startswith("cs_list_") and name[8:] in KINDS:
        return "list", name[8:]
    if not name.startswith("cs_") or "_" not in name[3:]:
        return None
    op, k = name[3:].rsplit("_", 1)
    return (op, k) if k in KINDS and op in OPS[1:] else None


def known(name):
    return name in SOLO or split(name) is not None


def supports(op, k):
    return k in ONLY.get(op, {k})


def rank(name):
    if name in SOLO:
        return 1, KINDS.index("grid" if name == "cs_grid" else "str"), 100 + list(SOLO).index(name)
    op, k = split(name)
    return 1, KINDS.index(k), OPS.index(op)


def helper(name):
    if name in SOLO:
        return SOLO[name]
    op, k = split(name)
    t, lst = ELEM[k], f"cs_list_{k}"
    eq = "strcmp(xs->data[i], v) == 0" if k == "str" else "xs->data[i] == v"
    lt = "strcmp(xs->data[i], m) {op} 0" if k == "str" else "xs->data[i] {op} m"
    std, both = ["stdlib.h"], ["stdlib.h", "string.h"]
    if op == "list":
        deps = ["cs_list_i64"] if k == "grid" else []
        return [], deps, f"""typedef struct
{{
    {ptr(t)}data;
    int len;
    int cap;
}} {lst};"""
    if op == "new":
        return std, [lst], f"""static {lst} *cs_new_{k}(void)
{{
    {lst} *xs = malloc(sizeof({lst}));
    xs->len = 0;
    xs->cap = 8;
    xs->data = malloc(8 * sizeof({t}));
    return xs;
}}"""
    if op == "push":
        return std, [lst], f"""static void cs_push_{k}({lst} *xs, {decl(t, "v")})
{{
    if (xs->len == xs->cap)
    {{
        xs->cap *= 2;
        xs->data = realloc(xs->data, xs->cap * sizeof({t}));
    }}
    xs->data[xs->len++] = v;
}}"""
    if op == "from":
        return [], [f"cs_new_{k}", f"cs_push_{k}"], f"""static {lst} *cs_from_{k}(int n, {decl(ptr(t), "v")})
{{
    {lst} *xs = cs_new_{k}();
    for (int i = 0; i < n; i++)
    {{
        cs_push_{k}(xs, v[i]);
    }}
    return xs;
}}"""
    if op == "pop":
        return [], [lst], f"""static {decl(t, f"cs_pop_{k}({lst} *xs)")}
{{
    xs->len--;
    return xs->data[xs->len];
}}"""
    if op == "pop_at":
        return [], [lst], f"""static {decl(t, f"cs_pop_at_{k}({lst} *xs, long long i)")}
{{
    {decl(t, "v")} = xs->data[i];
    for (long long j = i; j < xs->len - 1; j++)
    {{
        xs->data[j] = xs->data[j + 1];
    }}
    xs->len--;
    return v;
}}"""
    if op == "insert":
        return [], [f"cs_push_{k}"], f"""static void cs_insert_{k}({lst} *xs, long long i, {decl(t, "v")})
{{
    cs_push_{k}(xs, v);
    for (long long j = xs->len - 1; j > i; j--)
    {{
        xs->data[j] = xs->data[j - 1];
    }}
    xs->data[i] = v;
}}"""
    if op == "index_of":
        return (["string.h"] if k == "str" else []), [lst], f"""static long long cs_index_of_{k}({lst} *xs, {decl(t, "v")})
{{
    for (int i = 0; i < xs->len; i++)
    {{
        if ({eq})
        {{
            return i;
        }}
    }}
    return -1;
}}"""
    if op == "contains":
        return [], [f"cs_index_of_{k}"], f"""static int cs_contains_{k}({lst} *xs, {decl(t, "v")})
{{
    return cs_index_of_{k}(xs, v) >= 0;
}}"""
    if op == "cmp":
        if k == "str":
            return ["string.h"], [], """static int cs_cmp_str(const void *a, const void *b)
{
    return strcmp(*(const char *const *)a, *(const char *const *)b);
}"""
        return [], [], f"""static int cs_cmp_{k}(const void *a, const void *b)
{{
    {t} x = *(const {t} *)a;
    {t} y = *(const {t} *)b;
    return (x > y) - (x < y);
}}"""
    if op == "sort":
        return std, [lst, f"cs_cmp_{k}"], f"""static void cs_sort_{k}({lst} *xs)
{{
    qsort(xs->data, xs->len, sizeof({t}), cs_cmp_{k});
}}"""
    if op == "reverse":
        return [], [lst], f"""static void cs_reverse_{k}({lst} *xs)
{{
    for (int i = 0, j = xs->len - 1; i < j; i++, j--)
    {{
        {decl(t, "t")} = xs->data[i];
        xs->data[i] = xs->data[j];
        xs->data[j] = t;
    }}
}}"""
    if op == "sort_desc":
        return [], [f"cs_sort_{k}", f"cs_reverse_{k}"], f"""static void cs_sort_desc_{k}({lst} *xs)
{{
    cs_sort_{k}(xs);
    cs_reverse_{k}(xs);
}}"""
    if op == "slice":
        return [], [f"cs_new_{k}", f"cs_push_{k}"], f"""static {lst} *cs_slice_{k}({lst} *xs, long long a, long long b)
{{
    {lst} *r = cs_new_{k}();
    if (b > xs->len)
    {{
        b = xs->len;
    }}
    for (long long i = a; i < b; i++)
    {{
        cs_push_{k}(r, xs->data[i]);
    }}
    return r;
}}"""
    if op == "sorted":
        return [], [f"cs_slice_{k}", f"cs_sort_{k}"], f"""static {lst} *cs_sorted_{k}({lst} *xs)
{{
    {lst} *r = cs_slice_{k}(xs, 0, xs->len);
    cs_sort_{k}(r);
    return r;
}}"""
    if op == "sum":
        return [], [lst], f"""static {t} cs_sum_{k}({lst} *xs)
{{
    {t} s = 0;
    for (int i = 0; i < xs->len; i++)
    {{
        s += xs->data[i];
    }}
    return s;
}}"""
    if op in ("min", "max"):
        test = lt.format(op="<" if op == "min" else ">")
        return (["string.h"] if k == "str" else []), [lst], f"""static {decl(t, f"cs_{op}_{k}({lst} *xs)")}
{{
    {decl(t, "m")} = xs->data[0];
    for (int i = 1; i < xs->len; i++)
    {{
        if ({test})
        {{
            m = xs->data[i];
        }}
    }}
    return m;
}}"""
    if op == "fill":
        return [], [f"cs_new_{k}", f"cs_push_{k}"], f"""static {lst} *cs_fill_{k}(long long n, {decl(t, "v")})
{{
    {lst} *xs = cs_new_{k}();
    for (long long i = 0; i < n; i++)
    {{
        cs_push_{k}(xs, v);
    }}
    return xs;
}}"""
    if op == "show":
        item = ITEM[k]
        return both, [lst, *SHOWS.get(k, [])], f"""static const char *cs_show_{k}({lst} *xs)
{{
    int n = 3;
    for (int i = 0; i < xs->len; i++)
    {{
        n += strlen({item}) + 2;
    }}
    char *s = malloc(n);
    strcpy(s, "[");
    for (int i = 0; i < xs->len; i++)
    {{
        if (i > 0)
        {{
            strcat(s, ", ");
        }}
        strcat(s, {item});
    }}
    strcat(s, "]");
    return s;
}}"""
    raise KeyError(name)
