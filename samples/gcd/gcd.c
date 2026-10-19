#include <stdio.h>

long long gcd(long long a, long long b)
{
    while (b != 0)
    {
        long long t = b;
        b = a % b;
        a = t;
    }
    return a;
}

int main(void)
{
    printf("%lld\n", gcd(48, 18));
    return 0;
}
