package main

import (
    "fmt"
    "strings"
)

func describe(s string) string {
    t := strings.TrimSpace(s)
    first := strings.ToUpper(t[0:1])
    rest := strings.ToLower(t[1:])
    return first + rest
}

func count(s string, c rune) int64 {
    var n int64 = 0
    for _, ch := range s {
        if ch == c {
            n++
        }
    }
    return n
}

func main() {
    name := "  hELLO wORLD  "
    title := describe(name)
    fmt.Println(title, count(title, 'o'), strings.Index(title, "World"), strings.ReplaceAll(title, "World", "There"))
    fmt.Println("abc" < "abd", "b" > "a", strings.HasSuffix(title, "rld"))
}
