seen = set()
for x in [3, 1, 4, 1, 5, 9, 2, 6, 5, 3]:
    seen.add(x)
print(len(seen), 4 in seen, 7 in seen)
seen.discard(4)
seen.discard(100)
out = []
for v in sorted(seen):
    out.append(v)
print(out, len(seen))
words = set()
for w in "b a c a b".split():
    words.add(w)
print(len(words), "a" in words)
s = ""
for w in sorted(words):
    s += w
print(s)
