def mean(a, b):
    return (a + b) / 2


def area(r):
    return 3.25 * r * r


def scale(x, k):
    y = x * k
    y += 0.5
    y /= 2
    return y


def halve(n):
    return n / 2


x = 1.5
y = x * 4 - 0.25
n = 7
z = n / 2
w = int(y)
v = float(n) + x
tiny = 2.5e-3
print(mean(3, 4), area(2.0), scale(1.5, 3), halve(9))
print(y, z, w, v, -x, tiny * 4)
if y > n:
    print("big")
else:
    print("small")
