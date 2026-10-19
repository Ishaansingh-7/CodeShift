#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *cs_read_line(void)
{
    char buf[4096];
    if (fgets(buf, sizeof buf, stdin) == NULL)
    {
        buf[0] = '\0';
    }
    buf[strcspn(buf, "\r\n")] = '\0';
    char *s = malloc(strlen(buf) + 1);
    strcpy(s, buf);
    return s;
}

typedef struct
{
    long long *data;
    int len;
    int cap;
} cs_list_i64;

static cs_list_i64 *cs_new_i64(void)
{
    cs_list_i64 *xs = malloc(sizeof(cs_list_i64));
    xs->len = 0;
    xs->cap = 8;
    xs->data = malloc(8 * sizeof(long long));
    return xs;
}

static void cs_push_i64(cs_list_i64 *xs, long long v)
{
    if (xs->len == xs->cap)
    {
        xs->cap *= 2;
        xs->data = realloc(xs->data, xs->cap * sizeof(long long));
    }
    xs->data[xs->len++] = v;
}

static long long cs_max_i64(cs_list_i64 *xs)
{
    long long m = xs->data[0];
    for (int i = 1; i < xs->len; i++)
    {
        if (xs->data[i] > m)
        {
            m = xs->data[i];
        }
    }
    return m;
}

static cs_list_i64 *cs_s2ints(const char *s)
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
}

long long total(cs_list_i64 *nums)
{
    long long s = 0;
    for (int i = 0; i < nums->len; i++)
    {
        long long x = nums->data[i];
        s += x;
    }
    return s;
}

int main(void)
{
    const char *name = cs_read_line();
    cs_list_i64 *nums = cs_s2ints(cs_read_line());
    printf("Hello %s\n", name);
    printf("sum %lld max %lld\n", total(nums), cs_max_i64(nums));
    return 0;
}
