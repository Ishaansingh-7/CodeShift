#include <stdio.h>

long long power(long long b, long long e)
{
    if (e == 0)
    {
        return 1;
    }
    long long half = power(b, e / 2);
    if (e % 2 == 0)
    {
        return half * half;
    }
    return half * half * b;
}

int main(void)
{
    printf("%lld\n", power(2, 10));
    return 0;
}
