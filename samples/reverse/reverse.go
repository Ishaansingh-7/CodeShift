package main

import "fmt"

func reverse(s string) string {
    out := ""
    for _, ch := range s {
        out = string(ch) + out
    }
    return out
}

func main() {
    fmt.Println(reverse("CodeShift"))
}
