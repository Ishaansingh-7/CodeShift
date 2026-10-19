function bubble(xs) {
  for (let i = 0; i < xs.length; i++) {
    for (let j = 0; j < xs.length - 1 - i; j++) {
      if (xs[j] > xs[j + 1]) {
        [xs[j], xs[j + 1]] = [xs[j + 1], xs[j]];
      }
    }
  }
}

const xs = [5, 1, 4, 2, 8];
bubble(xs);
console.log(xs);
