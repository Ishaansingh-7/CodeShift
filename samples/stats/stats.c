#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static const char *cs_f2s(double x)
{
    static char buf[8][48];
    static int k = 0;
    char *s = buf[k++ % 8];
    double a = x < 0 ? -x : x;
    int sci = a != 0 && (a < 1e-4 || a >= 1e16);
    for (int p = 0; p <= 25; p++)
    {
        snprintf(s, 48, sci ? "%.*e" : "%.*f", p, x);
        if (strtod(s, NULL) == x)
        {
            break;
        }
    }
    if (strspn(s, "-0123456789") == strlen(s))
    {
        strcat(s, ".0");
    }
    return s;
}

double mean(long long xs[], int n)
{
    long long total = 0;
    for (int i = 0; i < n; i++)
    {
        long long x = xs[i];
        total += x;
    }
    return (double)total / (double)n;
}

double stdev(long long xs[], int n)
{
    double m = mean(xs, n);
    double s = 0.0;
    for (int i = 0; i < n; i++)
    {
        long long x = xs[i];
        s += ((double)x - m) * ((double)x - m);
    }
    return sqrt(s / (double)n);
}

int main(void)
{
    long long data[] = {2, 4, 4, 4, 5, 5, 7, 9};
    printf("%s %s %lld\n", cs_f2s(mean(data, 8)), cs_f2s(stdev(data, 8)), (long long)rint(stdev(data, 8)));
    return 0;
}
