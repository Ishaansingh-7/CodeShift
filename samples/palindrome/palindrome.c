#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

static const char *cs_append(const char *a, const char *b)
{
    char *s = malloc(strlen(a) + strlen(b) + 1);
    strcpy(s, a);
    strcat(s, b);
    return s;
}

static const char *cs_c2s(char c)
{
    char *s = malloc(2);
    s[0] = c;
    s[1] = '\0';
    return s;
}

static const char *cs_lower(const char *s)
{
    size_t n = strlen(s);
    char *out = malloc(n + 1);
    for (size_t i = 0; i <= n; i++)
    {
        out[i] = (char)tolower((unsigned char)s[i]);
    }
    return out;
}

const char *clean(const char *s)
{
    const char *out = "";
    const char *text = cs_lower(s);
    for (int i = 0; text[i] != '\0'; i++)
    {
        char ch = text[i];
        if (isalpha(ch))
        {
            out = cs_append(out, cs_c2s(ch));
        }
    }
    return out;
}

int is_palindrome(const char *s)
{
    const char *t = clean(s);
    int i = 0;
    for (int j = strlen(t) - 1; i < j; j--)
    {
        if (t[i] != t[j])
        {
            return 0;
        }
        i += 1;
    }
    return 1;
}

int main(void)
{
    printf("%d\n", is_palindrome("Never odd or even"));
    return 0;
}
