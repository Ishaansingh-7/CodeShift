package main

import "fmt"

func isPrime(n int64) bool {
    if n < 2 {
        return false
    }
    for i := int64(2); i*i <= n; i++ {
        if n%i == 0 {
            return false
        }
    }
    return true
}

func main() {
    fmt.Println(isPrime(97))
}
