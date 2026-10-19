#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

static const char *cs_i2s(long long n)
{
    static char buf[8][24];
    static int k = 0;
    char *s = buf[k++ % 8];
    snprintf(s, 24, "%lld", n);
    return s;
}

static const char *cs_concat(const char *a, const char *b)
{
    char *s = malloc(strlen(a) + strlen(b) + 1);
    strcpy(s, a);
    strcat(s, b);
    return s;
}

typedef struct
{
    const char **data;
    int len;
    int cap;
} cs_list_str;

static cs_list_str *cs_new_str(void)
{
    cs_list_str *xs = malloc(sizeof(cs_list_str));
    xs->len = 0;
    xs->cap = 8;
    xs->data = malloc(8 * sizeof(const char *));
    return xs;
}

static void cs_push_str(cs_list_str *xs, const char *v)
{
    if (xs->len == xs->cap)
    {
        xs->cap *= 2;
        xs->data = realloc(xs->data, xs->cap * sizeof(const char *));
    }
    xs->data[xs->len++] = v;
}

static int cs_cmp_str(const void *a, const void *b)
{
    return strcmp(*(const char *const *)a, *(const char *const *)b);
}

static void cs_sort_str(cs_list_str *xs)
{
    qsort(xs->data, xs->len, sizeof(const char *), cs_cmp_str);
}

static cs_list_str *cs_split_ws(const char *s)
{
    cs_list_str *xs = cs_new_str();
    int i = 0;
    while (s[i] != '\0')
    {
        while (s[i] != '\0' && isspace((unsigned char)s[i]))
        {
            i++;
        }
        int start = i;
        while (s[i] != '\0' && !isspace((unsigned char)s[i]))
        {
            i++;
        }
        if (i > start)
        {
            char *w = malloc(i - start + 1);
            memcpy(w, s + start, i - start);
            w[i - start] = '\0';
            cs_push_str(xs, w);
        }
    }
    return xs;
}

typedef struct
{
    const char **keys;
    long long *vals;
    int len;
    int cap;
} cs_map_str_i64;

static cs_map_str_i64 *cs_mnew_str_i64(void)
{
    cs_map_str_i64 *m = malloc(sizeof(cs_map_str_i64));
    m->len = 0;
    m->cap = 8;
    m->keys = malloc(8 * sizeof(const char *));
    m->vals = malloc(8 * sizeof(long long));
    return m;
}

static int cs_mfind_str_i64(cs_map_str_i64 *m, const char *k)
{
    for (int i = 0; i < m->len; i++)
    {
        if (strcmp(m->keys[i], k) == 0)
        {
            return i;
        }
    }
    return -1;
}

static void cs_mput_str_i64(cs_map_str_i64 *m, const char *k, long long v)
{
    int i = cs_mfind_str_i64(m, k);
    if (i < 0)
    {
        if (m->len == m->cap)
        {
            m->cap *= 2;
            m->keys = realloc(m->keys, m->cap * sizeof(const char *));
            m->vals = realloc(m->vals, m->cap * sizeof(long long));
        }
        i = m->len++;
        m->keys[i] = k;
    }
    m->vals[i] = v;
}

static long long cs_mget_str_i64(cs_map_str_i64 *m, const char *k)
{
    int i = cs_mfind_str_i64(m, k);
    return i < 0 ? 0 : m->vals[i];
}

static void cs_mincr_str_i64(cs_map_str_i64 *m, const char *k, long long v)
{
    int i = cs_mfind_str_i64(m, k);
    if (i < 0)
    {
        cs_mput_str_i64(m, k, v);
    }
    else
    {
        m->vals[i] += v;
    }
}

static cs_list_str *cs_mkeys_str_i64(cs_map_str_i64 *m)
{
    cs_list_str *r = cs_new_str();
    for (int i = 0; i < m->len; i++)
    {
        cs_push_str(r, m->keys[i]);
    }
    cs_sort_str(r);
    return r;
}

const char *word_count(const char *text)
{
    cs_map_str_i64 *counts = cs_mnew_str_i64();
    cs_list_str *items = cs_split_ws(text);
    for (int i = 0; i < items->len; i++)
    {
        const char *w = items->data[i];
        cs_mincr_str_i64(counts, w, 1);
    }
    const char *best = "";
    cs_list_str *items2 = cs_mkeys_str_i64(counts);
    for (int i = 0; i < items2->len; i++)
    {
        const char *w = items2->data[i];
        if (strcmp(best, "") == 0 || cs_mget_str_i64(counts, w) > cs_mget_str_i64(counts, best) || cs_mget_str_i64(counts, w) == cs_mget_str_i64(counts, best) && strcmp(w, best) < 0)
        {
            best = w;
        }
    }
    return cs_concat(cs_concat(best, " "), cs_i2s(cs_mget_str_i64(counts, best)));
}

int main(void)
{
    printf("%s\n", word_count("the cat and the hat and the bat"));
    return 0;
}
