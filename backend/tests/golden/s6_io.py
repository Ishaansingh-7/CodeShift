import sys


def report(name, scores):
    total = 0
    for s in scores:
        total += s
    avg = total / len(scores)
    return f"{name:<6}|{total:>5}|{avg:8.2f}"


n = int(input())
for i in range(n):
    name = input()
    scores = list(map(int, input().split()))
    print(report(name, scores))
print("pi is about", f"{3.14159:.3f}", end="")
print(" done")
x = float(input())
print(f"{x:.1f} and {x * 2:>7.2f}!")
tag = "ok"
print(f"[{n:4}] [{tag:>5}]")
sys.exit(0)
print("never")
