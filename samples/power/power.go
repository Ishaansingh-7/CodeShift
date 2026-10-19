package main

import "fmt"

func power(b, e int64) int64 {
    if e == 0 {
        return 1
    }
    half := power(b, e/2)
    if e%2 == 0 {
        return half * half
    }
    return half * half * b
}

func main() {
    fmt.Println(power(2, 10))
}
