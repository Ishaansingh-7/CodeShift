package main

import (
    "bufio"
    "fmt"
    "os"
    "slices"
    "strconv"
    "strings"
)

var csIn = bufio.NewReader(os.Stdin)

func csReadLine() string {
    s, _ := csIn.ReadString('\n')
    return strings.TrimRight(s, "\r\n")
}

func csInts(s string) []int64 {
    r := []int64{}
    for _, w := range strings.Fields(s) {
        v, _ := strconv.ParseInt(w, 10, 64)
        r = append(r, v)
    }
    return r
}

func total(nums []int64) int64 {
    var s int64 = 0
    for _, x := range nums {
        s += x
    }
    return s
}

func main() {
    name := csReadLine()
    nums := csInts(csReadLine())
    fmt.Println("Hello", name)
    fmt.Println("sum", total(nums), "max", slices.Max(nums))
}
