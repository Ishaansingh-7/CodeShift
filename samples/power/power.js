function power(b, e) {
  if (e === 0) {
    return 1;
  }
  const half = power(b, Math.floor(e / 2));
  if (e % 2 === 0) {
    return half * half;
  }
  return half * half * b;
}

console.log(power(2, 10));
