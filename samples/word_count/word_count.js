function csSplitWs(s) {
  return s.replaceAll("\t", " ").replaceAll("\n", " ").split(" ").filter((w) => w !== "");
}

function wordCount(text) {
  const counts = new Map();
  for (const w of csSplitWs(text)) {
    counts.set(w, (counts.get(w) ?? 0) + 1);
  }
  let best = "";
  for (const w of [...counts.keys()].sort()) {
    if (best === "" || counts.get(w) > counts.get(best) || counts.get(w) === counts.get(best) && w < best) {
      best = w;
    }
  }
  return best + " " + String(counts.get(best));
}

console.log(wordCount("the cat and the hat and the bat"));
