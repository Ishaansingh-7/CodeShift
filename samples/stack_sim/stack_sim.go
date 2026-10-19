package main

import "fmt"

func csPop[T any](xs *[]T) T {
    v := (*xs)[len(*xs)-1]
    *xs = (*xs)[:len(*xs)-1]
    return v
}

func run(ops []int64) []int64 {
    stack := []int64{}
    for _, x := range ops {
        if x > 0 {
            stack = append(stack, x)
        } else if len(stack) > 0 {
            csPop(&stack)
        }
    }
    return stack
}

func main() {
    fmt.Println(run([]int64{5, 3, 0, 8, 0, 0, 2, 7}))
}
