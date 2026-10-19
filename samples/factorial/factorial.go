package main

import "fmt"

func fact(n int64) int64 {
    if n <= 1 {
        return 1
    }
    return n * fact(n-1)
}

func main() {
    fmt.Println(fact(10))
}
