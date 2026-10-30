package main

import (
	"fmt"
	"sort"
)

func main() {
	x, y := 11, 6
	fmt.Println(x&y, x|y, x^y)
	fmt.Println(x<<3, 200>>2, ^x)
	flags := 0
	flags |= 4
	flags ^= 1
	flags &^= 4
	flags <<= 2
	fmt.Println(flags, 1<<40, 'z'-'a')
	ages := map[string]int{"amy": 30, "bob": 25}
	ages["cat"] = 41
	fmt.Println(ages["amy"]+ages["cat"], len(ages))
	xs := []int{5, 2, 9, 1}
	sort.Ints(xs)
	names := []string{"pear", "apple", "fig"}
	sort.Strings(names)
	fmt.Println(xs[0], xs[3], names[0])
	out := ""
	for i := 0; i < 3; i++ {
		out += string(rune('x' + i))
	}
	fmt.Println(out)
}
