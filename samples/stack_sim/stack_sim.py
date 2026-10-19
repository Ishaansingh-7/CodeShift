def run(ops):
    stack = []
    for x in ops:
        if x > 0:
            stack.append(x)
        elif len(stack) > 0:
            stack.pop()
    return stack

print(run([5, 3, 0, 8, 0, 0, 2, 7]))
