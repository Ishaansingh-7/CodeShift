import math

def mean(xs):
    total = 0
    for x in xs:
        total += x
    return total / len(xs)

def stdev(xs):
    m = mean(xs)
    s = 0.0
    for x in xs:
        s += (x - m) * (x - m)
    return math.sqrt(s / len(xs))

data = [2, 4, 4, 4, 5, 5, 7, 9]
print(mean(data), stdev(data), round(stdev(data)))
