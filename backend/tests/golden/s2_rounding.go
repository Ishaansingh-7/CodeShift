package main

import (
    "fmt"
    "math"
)

func csRoundJs(x float64) float64 {
    return math.Floor(x + 0.5)
}

func main() {
    fmt.Println(math.Round(2.5), math.Round(-2.5), csRoundJs(2.5), csRoundJs(-2.5), int64(math.RoundToEven(2.5)))
}
