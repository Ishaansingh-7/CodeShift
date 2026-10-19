package main

import (
    "fmt"
    "strings"
)

func csIsAlpha(c rune) bool {
    return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z'
}

func clean(s string) string {
    out := ""
    for _, ch := range strings.ToLower(s) {
        if csIsAlpha(ch) {
            out += string(ch)
        }
    }
    return out
}

func isPalindrome(s string) bool {
    t := clean(s)
    i := 0
    for j := len(t) - 1; i < j; j-- {
        if t[i] != t[j] {
            return false
        }
        i += 1
    }
    return true
}

func main() {
    fmt.Println(isPalindrome("Never odd or even"))
}
