#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

static double cs_round_js(double x)
{
    return floor(x + 0.5);
}

int main(void)
{
    printf("%s %s %s %s %lld\n", cs_f2s(round(2.5)), cs_f2s(round(-2.5)), cs_f2s(cs_round_js(2.5)), cs_f2s(cs_round_js(-2.5)), (long long)rint(2.5));
    return 0;
}
