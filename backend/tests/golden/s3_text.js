function describe(s) {
  const t = s.trim();
  const first = t.slice(0, 1).toUpperCase();
  const rest = t.slice(1).toLowerCase();
  return first + rest;
}

function count(s, c) {
  let n = 0;
  for (const ch of s) {
    if (ch === c) {
      n++;
    }
  }
  return n;
}

const name = "  hELLO wORLD  ";
const title = describe(name);
console.log(title, count(title, "o"), title.indexOf("World"), title.replaceAll("World", "There"));
console.log("abc" < "abd", "b" > "a", title.endsWith("rld"));
