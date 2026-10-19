def digits_sum(s):
    total = 0
    for ch in s:
        total += ord(ch) - ord("0")
    return total


def label(flag):
    return str(flag)


n = int("42")
m = int(" 17 ")
f = float("2.5")
k = int(9.99)
v = float(7)
print(n + m, f * 2, k, v)
print(str(123), str(n * 2), digits_sum("2024"))
print(chr(72), chr(105), ord("A"), chr(ord("a") + 1))
print(label(True), label(n > 50), str(2.5), str(-4))
