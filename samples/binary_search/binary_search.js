function search(xs, t) {
  let lo = 0, hi = xs.length - 1;
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (xs[mid] === t) {
      return mid;
    }
    if (xs[mid] < t) {
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return -1;
}

console.log(search([1, 3, 5, 7, 9, 11], 7));
