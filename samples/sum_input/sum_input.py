def total(nums):
    s = 0
    for x in nums:
        s += x
    return s

name = input()
nums = list(map(int, input().split()))
print("Hello", name)
print("sum", total(nums), "max", max(nums))
