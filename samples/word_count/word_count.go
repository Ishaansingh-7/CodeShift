package main

import (
    "fmt"
    "maps"
    "slices"
    "strconv"
    "strings"
)

func wordCount(text string) string {
    counts := map[string]int64{}
    for _, w := range strings.Fields(text) {
        counts[w]++
    }
    best := ""
    for _, w := range slices.Sorted(maps.Keys(counts)) {
        if best == "" || counts[w] > counts[best] || counts[w] == counts[best] && w < best {
            best = w
        }
    }
    return best + " " + strconv.FormatInt(counts[best], 10)
}

func main() {
    fmt.Println(wordCount("the cat and the hat and the bat"))
}
