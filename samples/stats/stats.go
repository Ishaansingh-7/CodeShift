package main

import (
    "fmt"
    "math"
)

func mean(xs []int64) float64 {
    var total int64 = 0
    for _, x := range xs {
        total += x
    }
    return float64(total) / float64(len(xs))
}

func stdev(xs []int64) float64 {
    m := mean(xs)
    s := 0.0
    for _, x := range xs {
        s += (float64(x) - m) * (float64(x) - m)
    }
    return math.Sqrt(s / float64(len(xs)))
}

func main() {
    data := []int64{2, 4, 4, 4, 5, 5, 7, 9}
    fmt.Println(mean(data), stdev(data), int64(math.RoundToEven(stdev(data))))
}
