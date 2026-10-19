#include <stdio.h>

long long fib(int n)
{
    long long a = 0, b = 1;
    for (int i = 0; i < n; i++)
    {
        long long t = b;
        b = a + b;
        a = t;
    }
    return a;
}

int main(void)
{
    printf("%lld\n", fib(10));
    return 0;
}
