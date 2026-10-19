def power(b, e):
    if e == 0:
        return 1
    half = power(b, e // 2)
    if e % 2 == 0:
        return half * half
    return half * half * b

print(power(2, 10))
