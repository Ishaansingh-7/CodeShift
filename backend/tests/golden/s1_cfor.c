#include <stdio.h>

long long squares(long long n)
{
    long long total = 0;
    for (long long i = 1; i * i <= n; i++)
    {
        if (i % 2 == 0)
        {
            continue;
        }
        total += i * i;
    }
    return total;
}

int main(void)
{
    printf("%lld\n", squares(50));
    return 0;
}
