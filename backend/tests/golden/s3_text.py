def describe(s):
    t = s.strip()
    first = t[0:1].upper()
    rest = t[1:].lower()
    return first + rest


def count(s, c):
    n = 0
    for ch in s:
        if ch == c:
            n += 1
    return n


name = "  hELLO wORLD  "
title = describe(name)
print(title, count(title, "o"), title.find("World"), title.replace("World", "There"))
print("abc" < "abd", "b" > "a", title.endswith("rld"))
