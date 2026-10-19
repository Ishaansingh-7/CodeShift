#include <stdio.h>

int search(long long xs[], int n, long long t)
{
    int lo = 0, hi = n - 1;
    while (lo <= hi)
    {
        int mid = (lo + hi) / 2;
        if (xs[mid] == t)
        {
            return mid;
        }
        if (xs[mid] < t)
        {
            lo = mid + 1;
        }
        else
        {
            hi = mid - 1;
        }
    }
    return -1;
}

int main(void)
{
    long long xs[] = {1, 3, 5, 7, 9, 11};
    printf("%d\n", search(xs, 6, 7));
    return 0;
}
