package main

import "fmt"

func csFill[T any](n int64, v T) []T {
    xs := make([]T, n)
    for i := range xs {
        xs[i] = v
    }
    return xs
}

func csGrid[T any](r, c int64, v T) [][]T {
    g := make([][]T, r)
    for i := range g {
        g[i] = csFill(c, v)
    }
    return g
}

func makeGrid(rows, cols int) [][]int64 {
    grid := csGrid(int64(rows), int64(cols), int64(0))
    for i := 0; i < rows; i++ {
        for j := 0; j < cols; j++ {
            grid[i][j] = int64((i + 1) * (j + 1))
        }
    }
    return grid
}

func matrixSum(rows, cols int64) int64 {
    grid := makeGrid(int(rows), int(cols))
    var total int64 = 0
    for _, row := range grid {
        for _, v := range row {
            total += v
        }
    }
    return total
}

func main() {
    fmt.Println(matrixSum(3, 4))
}
