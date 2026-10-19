function csReadLine() {
  if (!csReadLine.lines) {
    csReadLine.lines = require("fs").readFileSync(0, "utf8").split("\n");
    csReadLine.next = 0;
  }
  const line = csReadLine.lines[csReadLine.next++];
  return line === undefined ? "" : line.replace("\r", "");
}

function csSplitWs(s) {
  return s.replaceAll("\t", " ").replaceAll("\n", " ").split(" ").filter((w) => w !== "");
}

function total(nums) {
  let s = 0;
  for (const x of nums) {
    s += x;
  }
  return s;
}

const name = csReadLine();
const nums = csSplitWs(csReadLine()).map((w) => parseInt(w, 10));
console.log("Hello", name);
console.log("sum", total(nums), "max", Math.max(...nums));
