LIMIT = 10


def power(b, e=2):
    r = 1
    for _ in range(e):
        r *= b
    return r


def sign(x):
    return "pos" if x > 0 else "neg"


def inside(x):
    return 1 < x < LIMIT


def find(xs, t):
    for x in xs:
        if x == t:
            print("found", t)
            break
    else:
        print("missing", t)


def name(n):
    match n:
        case 1:
            return "one"
        case 2 | 3:
            return "few"
        case _:
            return "many"


def squares(n):
    return [i * i for i in range(n) if i % 2 == 0]


def main():
    a = b = 3
    xs = [5, 2, 9, 4]
    total = 0
    for i, x in enumerate(xs):
        total += i * x
    pairs = 0
    for x, y in zip(xs, [1, 2, 3]):
        pairs += x * y
    d = {"a": 1, "b": 2}
    keys = 0
    for k, v in d.items():
        keys += v
    vals = 0
    for v in d.values():
        vals += v
    back = []
    for x in reversed(xs):
        back.append(x)
    table = {k: k * k for k in range(4)}
    seen = {3, 1, 3}
    xs.remove(2)
    xs.extend([7, 8])
    print(power(5), power(2, e=10), sign(-3), "in" if inside(5) else "out", a + b)
    print(total, pairs, keys, vals, back[0], table[3], len(seen), xs[-1], len(xs))
    big = "some big" if any(x > 8 for x in xs) else "none big"
    print(sum(squares(7)), big, "all over 1" if all(x > 1 for x in xs) else "not all")
    print("%d items, %.2f each" % (3, 2.5), "{} + {} = {}".format(1, 2, 3))
    print("a", "b", "c", sep="-")
    print("banana".count("an"), name(3), "hello"[-1])
    find(xs, 9)
    find(xs, 8)


main()
