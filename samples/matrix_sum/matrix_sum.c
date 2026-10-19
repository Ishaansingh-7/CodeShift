#include <stdio.h>
#include <stdlib.h>

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

static cs_list_i64 *cs_fill_i64(long long n, long long v)
{
    cs_list_i64 *xs = cs_new_i64();
    for (long long i = 0; i < n; i++)
    {
        cs_push_i64(xs, v);
    }
    return xs;
}

typedef struct
{
    cs_list_i64 **data;
    int len;
    int cap;
} cs_list_grid;

static cs_list_grid *cs_new_grid(void)
{
    cs_list_grid *xs = malloc(sizeof(cs_list_grid));
    xs->len = 0;
    xs->cap = 8;
    xs->data = malloc(8 * sizeof(cs_list_i64 *));
    return xs;
}

static void cs_push_grid(cs_list_grid *xs, cs_list_i64 *v)
{
    if (xs->len == xs->cap)
    {
        xs->cap *= 2;
        xs->data = realloc(xs->data, xs->cap * sizeof(cs_list_i64 *));
    }
    xs->data[xs->len++] = v;
}

static cs_list_grid *cs_grid(long long r, long long c, long long v)
{
    cs_list_grid *g = cs_new_grid();
    for (long long i = 0; i < r; i++)
    {
        cs_push_grid(g, cs_fill_i64(c, v));
    }
    return g;
}

cs_list_grid *make_grid(int rows, int cols)
{
    cs_list_grid *grid = cs_grid(rows, cols, 0);
    for (int i = 0; i < rows; i++)
    {
        for (int j = 0; j < cols; j++)
        {
            grid->data[i]->data[j] = ((long long)i + 1) * (j + 1);
        }
    }
    return grid;
}

long long matrix_sum(long long rows, long long cols)
{
    cs_list_grid *grid = make_grid(rows, cols);
    long long total = 0;
    for (int i = 0; i < grid->len; i++)
    {
        cs_list_i64 *row = grid->data[i];
        for (int i2 = 0; i2 < row->len; i2++)
        {
            long long v = row->data[i2];
            total += v;
        }
    }
    return total;
}

int main(void)
{
    printf("%lld\n", matrix_sum(3, 4));
    return 0;
}
