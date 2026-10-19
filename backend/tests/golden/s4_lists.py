def evens(n):
    out = []
    for i in range(n):
        if i % 2 == 0:
            out.append(i)
    return out


def top(xs, k):
    ys = sorted(xs)
    ys.reverse()
    return ys[:k]


def longest(text):
    words = text.split()
    best = ""
    for w in words:
        if len(w) > len(best):
            best = w
    return best


nums = [5, 3, 8, 1, 9, 2]
e = evens(10)
print(e, len(e), sum(e), min(nums), max(nums))
nums.append(7)
nums.insert(0, 4)
last = nums.pop()
first = nums.pop(0)
print(nums, last, first, 8 in nums, 6 in nums, nums.index(8) if 8 in nums else -1)
nums.sort()
print(nums, top(nums, 3), nums[1:4])
del nums[0]
nums.sort(reverse=True)
print(nums, len(nums))
names = "ada grace alan".split()
print(", ".join(names), longest("the quick brown fox"))
scores = [1.5, 2.5, 4.0]
print(sum(scores), max(scores))
zeros = [0] * 4
zeros[2] = 9
print(zeros)
