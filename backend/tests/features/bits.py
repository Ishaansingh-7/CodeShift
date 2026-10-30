def popcount(n):
    count = 0
    while n > 0:
        count += n & 1
        n >>= 1
    return count


x = 0b1011
y = 6
print(x & y, x | y, x ^ y)
print(x << 3, 200 >> 2, ~x, -9 >> 1)
print(1 << 40)
flags = 0
flags |= 4
flags |= 1
flags ^= 4
flags &= 7
flags <<= 2
print(flags)
mask = 0
for bit in range(5):
    mask = mask | (1 << bit)
print(mask, mask >> 1 + 1, popcount(mask), popcount(1023 & ~mask))
for k in range(1, 9):
    if (k & (k - 1)) == 0:
        print(k, "is a power of two")
