def word_count(text):
    counts = {}
    for w in text.split():
        counts[w] = counts.get(w, 0) + 1
    best = ""
    for w in sorted(counts):
        if best == "" or counts[w] > counts[best] or counts[w] == counts[best] and w < best:
            best = w
    return best + " " + str(counts[best])

print(word_count("the cat and the hat and the bat"))
