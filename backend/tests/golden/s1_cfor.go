package main

import "fmt"

func squares(n int64) int64 {
    var total int64 = 0
    for i := int64(1); i*i <= n; i++ {
        if i%2 == 0 {
            continue
        }
        total += i * i
    }
    return total
}

func main() {
    fmt.Println(squares(50))
}
