#include <stdio.h>

#define N 5
#define RATE 2.5
const int LIMIT = 10;
int base = 3;

int scale(int x)
{
    return x * LIMIT + base;
}

int main(void)
{
    int a[N];
    int b[4] = {0};
    int c[5] = {1, 2};
    int g[2][3] = {{1, 2, 3}, {4, 5, 6}};
    int z[2][2];
    for (int i = 0; i < N; i++)
    {
        a[i] = i * i;
    }
    int n = sizeof(c) / sizeof(c[0]);
    z[1][1] = 7;
    printf("%d %d %d %d %d %d %d\n", a[4], b[3], c[1] + c[4], n, g[1][2], z[1][1], scale(2));
    printf("%.1f\n", RATE * 2);
    return 0;
}
