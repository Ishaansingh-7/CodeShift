def clean(s):
    out = ""
    for ch in s.lower():
        if ch.isalpha():
            out += ch
    return out

def is_palindrome(s):
    t = clean(s)
    i = 0
    j = len(t) - 1
    while i < j:
        if t[i] != t[j]:
            return False
        i += 1
        j -= 1
    return True

print(is_palindrome("Never odd or even"))
