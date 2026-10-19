#include <stdio.h>

long long fact(long long n)
{
    if (n <= 1)
    {
        return 1;
    }
    return n * fact(n - 1);
}

int main(void)
{
    printf("%lld\n", fact(10));
    return 0;
}
