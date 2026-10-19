package main

import "fmt"

func bubble(xs []int64) {
    for i := 0; i < len(xs); i++ {
        for j := 0; j < len(xs)-1-i; j++ {
            if xs[j] > xs[j+1] {
                xs[j], xs[j+1] = xs[j+1], xs[j]
            }
        }
    }
}

func main() {
    xs := []int64{5, 1, 4, 2, 8}
    bubble(xs)
    fmt.Println(xs)
}
