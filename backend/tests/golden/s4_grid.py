def make(r, c):
    g = [[0] * c for _ in range(r)]
    for i in range(r):
        for j in range(c):
            g[i][j] = i * c + j
    return g


def total(g):
    s = 0
    for row in g:
        for v in row:
            s += v
    return s


g = make(3, 4)
print(len(g), len(g[0]), g[2][3], total(g))
g[1][1] = 100
print(g[1], total(g))
