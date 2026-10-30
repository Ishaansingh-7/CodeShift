package main

import (
    "fmt"
    "strconv"
)

const (
    A = iota
    B
    C
)

const LIMIT = 10

var base = 3

func grade(n int) string {
    switch {
    case n >= 90:
        return "A"
    case n >= 50:
        return "B"
    default:
        return "C"
    }
}

func name(d int) string {
    switch d {
    case 1:
        return "one"
    case 2, 3:
        return "few"
    default:
        return "many"
    }
}

func main() {
    xs := make([]int, 3)
    xs[1] = 5
    var a [4]int
    a[2] = 7
    ys := []int{}
    ys = append(ys, 1, 2, 3)
    m := map[string]int{}
    m["a"] = 1
    m["b"] = 2
    total := 0
    for _, v := range m {
        total += v
    }
    keys := 0
    for k := range m {
        keys += len(k)
    }
    idx := 0
    for i, y := range ys {
        idx += i * y
    }
    n, _ := strconv.Atoi("42")
    if q := n / 2; q > 20 {
        fmt.Println("big", q)
    }
    fmt.Printf("%d %d %d %d %d %d %s\n", xs[1], a[2], len(ys), total, keys, idx, strconv.Itoa(n))
    fmt.Println(C, LIMIT*base, grade(75), name(3))
}
