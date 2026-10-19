import math


def cs_round_away(x):
    r = math.floor(abs(x) + 0.5)
    return float(r if x >= 0 else -r)


def cs_round_js(x):
    return float(math.floor(x + 0.5))


print(cs_round_away(2.5), cs_round_away(-2.5), cs_round_js(2.5), cs_round_js(-2.5), round(2.5))
