function mean(a, b) {
  return (a + b) / 2;
}

function area(r) {
  return 3.25 * r * r;
}

function scale(x, k) {
  let y = x * k;
  y += 0.5;
  y /= 2;
  return y;
}

function halve(n) {
  return n / 2;
}

const x = 1.5;
const y = x * 4 - 0.25;
const n = 7;
const z = n / 2;
const w = Math.trunc(y);
const v = n + x;
const tiny = 2.5e-3;
console.log(mean(3, 4), area(2.0), scale(1.5, 3), halve(9));
console.log(y, z, w, v, -x, tiny * 4);
if (y > n) {
  console.log("big");
} else {
  console.log("small");
}
