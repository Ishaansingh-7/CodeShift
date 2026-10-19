def count_words(text):
    counts = {}
    for w in text.split():
        counts[w] = counts.get(w, 0) + 1
    return counts


def top_word(counts):
    best = ""
    for w in sorted(counts):
        if best == "" or counts[w] > counts[best]:
            best = w
    return best


counts = count_words("the cat and the hat and the bat")
print(len(counts), counts["the"], counts.get("dog", 0), "cat" in counts, "dog" in counts)
print(top_word(counts))
counts["cat"] = 10
del counts["hat"]
print(len(counts), counts["cat"], "hat" in counts)
total = 0
for w in counts:
    total += counts[w]
print(total)
squares = {}
for i in range(5):
    squares[i] = i * i
squares[2] += 100
print(squares[2], squares[4], len(squares))
names = {}
names[1] = "one"
names[2] = "two"
print(names[1] + names[2], names.get(3, "none"))
