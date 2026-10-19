#include <stdio.h>
#include <string.h>

void reverse(const char *s, char *out)
{
    int n = strlen(s);
    for (int i = 0; i < n; i++)
    {
        out[n - 1 - i] = s[i];
    }
    out[n] = '\0';
}

int main(void)
{
    char out[32];
    reverse("CodeShift", out);
    printf("%s\n", out);
    return 0;
}
