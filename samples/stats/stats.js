function csRoundEven(x) {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

function mean(xs) {
  let total = 0;
  for (const x of xs) {
    total += x;
  }
  return total / xs.length;
}

function stdev(xs) {
  const m = mean(xs);
  let s = 0.0;
  for (const x of xs) {
    s += (x - m) * (x - m);
  }
  return Math.sqrt(s / xs.length);
}

const data = [2, 4, 4, 4, 5, 5, 7, 9];
console.log(mean(data), stdev(data), Math.trunc(csRoundEven(stdev(data))));
