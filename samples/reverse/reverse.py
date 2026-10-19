def reverse(s):
    out = ""
    for ch in s:
        out = ch + out
    return out

print(reverse("CodeShift"))
