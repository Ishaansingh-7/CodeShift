import math


def hyp(a, b):
    return math.sqrt(a * a + b * b)


def clamp(n, lo, hi):
    return max(lo, min(n, hi))


x = -3.75
n = -7
print(abs(n), abs(x), min(4, 9), max(2.5, 1.5), clamp(15, 0, 10))
print(2 ** 10, 3 ** 4, 2.0 ** 0.5, pow(5, 3))
print(math.floor(x), math.ceil(x), math.trunc(x), round(2.5), round(3.5), round(-2.5))
print(hyp(3, 4), math.hypot(5, 12), math.sqrt(2))
print(math.sin(0), math.cos(0), math.tan(0.5), math.atan2(1, 1))
print(math.log(math.e), math.log10(1000), math.log2(8), math.exp(1))
print(math.pi, 7.0 // 2, -7.5 // 2)
