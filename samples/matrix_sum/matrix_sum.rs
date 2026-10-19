fn make_grid(rows: i64, cols: i64) -> Vec<Vec<i64>> {
    let mut grid = vec![vec![0; cols as usize]; rows as usize];
    for i in 0..rows {
        for j in 0..cols {
            grid[i as usize][j as usize] = (i + 1) * (j + 1);
        }
    }
    grid
}

fn matrix_sum(rows: i64, cols: i64) -> i64 {
    let grid = make_grid(rows, cols);
    let mut total = 0;
    for row in grid.iter().cloned() {
        for &v in row.iter() {
            total += v;
        }
    }
    total
}

fn main() {
    println!("{}", matrix_sum(3, 4));
}
