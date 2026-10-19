package main

import "fmt"

func sumDigits(n int64) int64 {
    var total int64 = 0
    for n > 0 {
        total += n % 10
        n /= 10
    }
    return total
}

func main() {
    fmt.Println(sumDigits(4096))
}
