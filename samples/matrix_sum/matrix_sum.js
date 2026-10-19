function makeGrid(rows, cols) {
  const grid = Array.from({ length: rows }, () => new Array(cols).fill(0));
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      grid[i][j] = (i + 1) * (j + 1);
    }
  }
  return grid;
}

function matrixSum(rows, cols) {
  const grid = makeGrid(rows, cols);
  let total = 0;
  for (const row of grid) {
    for (const v of row) {
      total += v;
    }
  }
  return total;
}

console.log(matrixSum(3, 4));
