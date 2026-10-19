def first_neg(xs):
    k = -1
    for i in range(len(xs)):
        if xs[i] < 0:
            k = i
            break
    return k


def count_odd(n):
    c = 0
    for i in range(n):
        if i % 2 == 0:
            continue
        c += 1
    return c


def find_power(limit):
    p = 1
    while True:
        p = p * 2
        if p > limit:
            break
    return p


def skip_while(n):
    i = 0
    total = 0
    while i < n:
        i += 1
        if i % 3 == 0:
            continue
        total += i
    return total


def grade(score):
    if score >= 90:
        return 4
    elif score >= 75:
        return 3
    elif score >= 50:
        return 2
    return 1


def has_char(s, c):
    found = False
    for ch in s:
        if ch == c:
            found = True
            break
    if found:
        return 1
    return 0


print(first_neg([3, 1, -4, 1]), count_odd(10), find_power(100), skip_while(10))
print(grade(95), grade(80), grade(60), grade(10), has_char("hello", "l"), has_char("hello", "z"))
