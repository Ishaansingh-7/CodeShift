#include <stdio.h>
#include <string.h>

int digit_sum(char s[]) {
    int total = 0;
    for (int i = 0; i < strlen(s); i++) {
        total += s[i] - '0';
    }
    return total;
}

int main(void) {
    long long x = 11, y = 6;
    printf("%lld %lld %lld\n", x & y, x | y, x ^ y);
    printf("%lld %lld %lld\n", x << 3, 200 >> 2, ~x);
    long long flags = 0;
    flags |= 4;
    flags ^= 1;
    flags &= ~4;
    flags <<= 2;
    printf("%lld %lld\n", flags, 1LL << 40);
    puts("letters");
    for (char c = 'a'; c <= 'e'; c++) {
        putchar(c);
    }
    putchar('\n');
    for (int i = 0; i < 3; i++) {
        char ch = 'x' + i;
        printf("%c", ch);
    }
    printf("\n");
    char d = 'A';
    d += 2;
    d++;
    printf("%c %d %d\n", d, 'z' - 'a', digit_sum("4096"));
    int steps = 0;
    for (int i = 0, j = 10; i < j; i++, j--) {
        steps++;
    }
    printf("%d\n", steps);
    return 0;
}
