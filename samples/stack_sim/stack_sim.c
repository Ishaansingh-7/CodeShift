#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *cs_i2s(long long n)
{
    static char buf[8][24];
    static int k = 0;
    char *s = buf[k++ % 8];
    snprintf(s, 24, "%lld", n);
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

static cs_list_i64 *cs_from_i64(int n, long long *v)
{
    cs_list_i64 *xs = cs_new_i64();
    for (int i = 0; i < n; i++)
    {
        cs_push_i64(xs, v[i]);
    }
    return xs;
}

static long long cs_pop_i64(cs_list_i64 *xs)
{
    xs->len--;
    return xs->data[xs->len];
}

static const char *cs_show_i64(cs_list_i64 *xs)
{
    int n = 3;
    for (int i = 0; i < xs->len; i++)
    {
        n += strlen(cs_i2s(xs->data[i])) + 2;
    }
    char *s = malloc(n);
    strcpy(s, "[");
    for (int i = 0; i < xs->len; i++)
    {
        if (i > 0)
        {
            strcat(s, ", ");
        }
        strcat(s, cs_i2s(xs->data[i]));
    }
    strcat(s, "]");
    return s;
}

cs_list_i64 *run(cs_list_i64 *ops)
{
    cs_list_i64 *stack = cs_new_i64();
    for (int i = 0; i < ops->len; i++)
    {
        long long x = ops->data[i];
        if (x > 0)
        {
            cs_push_i64(stack, x);
        }
        else if (stack->len > 0)
        {
            cs_pop_i64(stack);
        }
    }
    return stack;
}

int main(void)
{
    printf("%s\n", cs_show_i64(run(cs_from_i64(8, (long long[]){5, 3, 0, 8, 0, 0, 2, 7}))));
    return 0;
}
