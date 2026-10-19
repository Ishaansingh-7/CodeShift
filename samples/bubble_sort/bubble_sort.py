def bubble(xs):
    for i in range(len(xs)):
        for j in range(len(xs) - 1 - i):
            if xs[j] > xs[j + 1]:
                xs[j], xs[j + 1] = xs[j + 1], xs[j]

xs = [5, 1, 4, 2, 8]
bubble(xs)
print(xs)
