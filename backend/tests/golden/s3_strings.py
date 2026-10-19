def shout(s):
    return s.upper() + "!"


def initials(name):
    out = ""
    for ch in name:
        if ch.isupper():
            out += ch
    return out


def vowels(s):
    n = 0
    for ch in s.lower():
        if ch in "aeiou":
            n += 1
    return n


word = "  CodeShift  "
t = word.strip()
print(shout(t), t.lower(), initials("Grace Brewster Hopper"), vowels(t))
print(t[0:4], t[4:], t[:2], len(t), t.find("Shift"), t.find("x"))
print(t.startswith("Code"), t.endswith("ift"), "Shift" in t, "z" in t)
print(t.replace("Shift", "Base"), "ab" * 3, "-" * 5)
print("apple" < "banana", "pear" > "peach", "pear" < "peach", t == "CodeShift")
digits = 0
spaces = 0
for c in "a1 b2 c3":
    if c.isdigit():
        digits += 1
    elif c.isspace():
        spaces += 1
print(digits, spaces, "q".upper(), "Q".lower())
