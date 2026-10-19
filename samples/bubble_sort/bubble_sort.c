#include <stdio.h>

void bubble(long long xs[], int n)
{
    for (int i = 0; i < n; i++)
    {
        for (int j = 0; j < n - 1 - i; j++)
        {
            if (xs[j] > xs[j + 1])
            {
                long long t = xs[j];
                xs[j] = xs[j + 1];
                xs[j + 1] = t;
            }
        }
    }
}

int main(void)
{
    long long xs[] = {5, 1, 4, 2, 8};
    bubble(xs, 5);
    for (int i = 0; i < 5; i++)
    {
        printf("%lld ", xs[i]);
    }
    return 0;
}
