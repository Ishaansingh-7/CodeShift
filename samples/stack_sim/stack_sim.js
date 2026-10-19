function run(ops) {
  const stack = [];
  for (const x of ops) {
    if (x > 0) {
      stack.push(x);
    } else if (stack.length > 0) {
      stack.pop();
    }
  }
  return stack;
}

console.log(run([5, 3, 0, 8, 0, 0, 2, 7]));
