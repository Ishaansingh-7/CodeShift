#include <stdio.h>

int is_prime(long long n)
{
    if (n < 2)
    {
        return 0;
    }
    for (long long i = 2; i * i <= n; i++)
    {
        if (n % i == 0)
        {
            return 0;
        }
    }
    return 1;
}

int main(void)
{
    printf("%d\n", is_prime(97));
    return 0;
}
