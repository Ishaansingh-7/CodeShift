def make_grid(rows, cols):
    grid = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            grid[i][j] = (i + 1) * (j + 1)
    return grid

def matrix_sum(rows, cols):
    grid = make_grid(rows, cols)
    total = 0
    for row in grid:
        for v in row:
            total += v
    return total

print(matrix_sum(3, 4))
