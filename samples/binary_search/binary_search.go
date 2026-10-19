package main

import "fmt"

func search(xs []int64, t int64) int {
    lo, hi := 0, len(xs)-1
    for lo <= hi {
        mid := (lo + hi) / 2
        if xs[mid] == t {
            return mid
        }
        if xs[mid] < t {
            lo = mid + 1
        } else {
            hi = mid - 1
        }
    }
    return -1
}

func main() {
    fmt.Println(search([]int64{1, 3, 5, 7, 9, 11}, 7))
}
