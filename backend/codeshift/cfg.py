def split(code):
    starts = {0}
    for k, ins in enumerate(code):
        if ins.op == "label":
            starts.add(k)
        elif ins.op in ("goto", "iffalse", "ret"):
            starts.add(k + 1)
    order = sorted(s for s in starts if s < len(code))
    blocks = [code[a:b] for a, b in zip(order, order[1:] + [len(code)])]
    where = {blk[0].name: b for b, blk in enumerate(blocks) if blk[0].op == "label"}
    succ = []
    for b, blk in enumerate(blocks):
        last = blk[-1]
        nxt = [b + 1] if b + 1 < len(blocks) else []
        if last.op == "goto":
            succ.append([where[last.name]])
        elif last.op == "iffalse":
            succ.append(nxt + [where[last.name]])
        elif last.op == "ret":
            succ.append([])
        else:
            succ.append(nxt)
    preds = [[] for _ in blocks]
    for b, ss in enumerate(succ):
        for s in ss:
            preds[s].append(b)
    return blocks, succ, preds


def reachable(succ):
    seen, work = set(), [0] if succ else []
    while work:
        b = work.pop()
        if b not in seen:
            seen.add(b)
            work += succ[b]
    return seen


def loops(succ, preds):
    heads, body = set(), set()
    for u, ss in enumerate(succ):
        for h in ss:
            if h <= u:
                heads.add(h)
                seen, work = {h}, [u]
                while work:
                    x = work.pop()
                    if x not in seen:
                        seen.add(x)
                        work += preds[x]
                body |= seen - {h}
    return heads, body


def graph(funcs, optimized):
    out, edges, base = [], [], 0
    for code in funcs:
        fn = code[0].name
        body = [i for i in code[1:] if not (optimized and i.dead)]
        if not body:
            continue
        blocks, succ, preds = split(body)
        heads, inner = loops(succ, preds)
        bid = lambda b: f"B{base + b}"
        for b, blk in enumerate(blocks):
            role = f"{fn} entry" if b == 0 else "loop head" if b in heads else "loop body" if b in inner \
                else "return" if blk[-1].op == "ret" else "block"
            lines = []
            for ins in blk:
                if ins.op == "iffalse":
                    lines.append(f"ifFalse {ins.args[0]} → {bid(succ[b][-1])}")
                elif ins.op not in ("label", "goto"):
                    lines.append(ins.text.strip())
            if not lines and blk[-1].op == "goto":
                lines.append(f"goto → {bid(succ[b][0])}")
            out.append({"id": bid(b), "title": f"{bid(b)} · {role}", "fn": fn, "lines": lines})
            for k, s in enumerate(succ[b]):
                label = "back" if s <= b else ("true" if k == 0 else "false") if blk[-1].op == "iffalse" else ""
                edges.append({"from": bid(b), "to": bid(s), "label": label})
        base += len(blocks)
    return {"blocks": out, "edges": edges}
