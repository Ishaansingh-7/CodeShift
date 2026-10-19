#include <stdio.h>

long long sum_digits(long long n)
{
    long long total = 0;
    while (n > 0)
    {
        total += n % 10;
        n /= 10;
    }
    return total;
}

int main(void)
{
    printf("%lld\n", sum_digits(4096));
    return 0;
}
