# Samples

Fifteen programs, each written in all six languages (the first nine are the core subset; the last six use the standard-library layer). These are both the Samples page content and the golden test suite: a translation is correct when it reproduces these files and their output.

| Folder | Sample | Covers |
|---|---|---|
| fib | Fibonacci | loops, parallel assignment, 64-bit overflow |
| gcd | Euclid's GCD | while, `%` sign rule on negatives |
| factorial | Factorial | recursion, overflow |
| is_prime | Prime check | early return, booleans |
| power | Fast power | recursion, integer division, overflow |
| sum_digits | Sum of digits | `%`, integer division |
| bubble_sort | Bubble sort | arrays, nested loops, swap |
| binary_search | Binary search | arrays, while, midpoint |
| reverse | Reverse a string | strings, for-each, building output |
| stats | Mean and deviation | floats, sqrt, round |
| palindrome | Palindrome check | string methods, lower, isalpha |
| matrix_sum | Matrix sum | 2D grid, nested for-each |
| stack_sim | Stack simulator | push / pop on a dynamic list |
| word_count | Word count | split, dict counter, string compare |
| sum_input | Sum input | input(), int(input()), reading a list of ints |

`tests.json` holds, per sample:
- `files`: file name per language (Java is always `Main.java`).
- `groups` / `lineGroups`: construct names, and the group id of every line in each language file (`null` = blank line). Same id = corresponding lines.
- `programStdout`: what each file prints when run as-is. C bubble sort prints `1 2 4 5 8 ` with a trailing space and no newline.
- `differential`: 5 inputs to the main function, with the expected output per language. For a program that reads standard input (`sum_input`) the inputs are stdin texts, and `stdin` holds the default one. The mismatches are real (JS float precision, C/Java/Go wraparound, Rust overflow panic, `%` sign rule).
- `ir`: expected three-address IR with optimizer tags.
