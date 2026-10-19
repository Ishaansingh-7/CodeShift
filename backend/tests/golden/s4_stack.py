def push_all(stack, items):
    for x in items:
        stack.append(x)


def drain(stack):
    total = 0
    while len(stack) > 0:
        total += stack.pop()
    return total


def words_sorted(text):
    ws = text.split(",")
    ws.sort()
    return ws


st = []
push_all(st, [4, 5, 6])
st.append(10)
print(st, len(st))
total = drain(st)
print(total, len(st))
fruits = words_sorted("pear,apple,fig")
print(fruits, "fig" in fruits, "kiwi" in fruits, fruits.index("pear"))
fruits[0] = "avocado"
fruits.insert(1, "banana")
print(" ".join(fruits), min(fruits), max(fruits))
temps = [3.5, -1.25, 2.0]
temps.sort()
print(temps, min(temps), sorted(temps)[2])
flags = [True, False, True]
flags[1] = True
print(flags, len(flags))
grid = [[1, 2], [3, 4]]
grid[0][1] += 5
grid.append([5, 6])
print(grid[0], len(grid), grid[2][1])
