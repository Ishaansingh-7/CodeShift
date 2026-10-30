function popcount(n) {
  let count = 0;
  while (n > 0) {
    count += n & 1;
    n >>= 1;
  }
  return count;
}

const x = 11, y = 6;
console.log(x & y, x | y, x ^ y);
console.log(x << 3, 200 >> 2, ~x);
let flags = 0;
flags |= 4;
flags ^= 1;
flags &= ~4;
flags <<= 2;
console.log(flags, popcount(255));
const xs = [1, 2, 3];
xs.unshift(0);
const first = xs.shift();
console.log(first, xs.length, xs[0]);
const p = { x: 3, y: 4 };
p.z = 10;
let total = 0;
for (const k in p) {
  total += p[k];
}
const s = new Set([1, 2, 2, 3]);
console.log(p.x + p.y, total, s.size);
