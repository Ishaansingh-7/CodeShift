function csRoundEven(x) {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

function csRoundAway(x) {
  return Math.sign(x) * Math.round(Math.abs(x));
}

console.log(csRoundAway(2.5), csRoundAway(-2.5), Math.round(2.5), Math.round(-2.5), csRoundEven(2.5));
