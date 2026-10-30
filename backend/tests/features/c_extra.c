#include <stdio.h>

int main(void)
{
    int a = 4, b = 9;
    int m = a > b ? a : b;
    int x, y;
    x = y = 3;
    int i = 0;
    do
    {
        i += 3;
    } while (i < 10);
    int d = 2;
    switch (d)
    {
        case 1:
            printf("one\n");
            break;
        case 2:
        case 3:
            printf("two or three\n");
            break;
        default:
            printf("other\n");
    }
    printf("%d %d %d %d\n", m, x, y, i);
    return 0;
}
