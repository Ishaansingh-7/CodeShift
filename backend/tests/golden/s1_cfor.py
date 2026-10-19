def squares(n):
    total = 0
    i = 1
    while i * i <= n:
        if i % 2 == 0:
            i += 1
            continue
        total += i * i
        i += 1
    return total


print(squares(50))
