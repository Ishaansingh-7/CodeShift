fn mean(xs: &[i64]) -> f64 {
    let mut total = 0i64;
    for &x in xs.iter() {
        total += x;
    }
    total as f64 / xs.len() as f64
}

fn stdev(xs: &[i64]) -> f64 {
    let m = mean(xs);
    let mut s = 0.0;
    for &x in xs.iter() {
        s += (x as f64 - m) * (x as f64 - m);
    }
    (s / xs.len() as f64).sqrt()
}

fn main() {
    let data = vec![2, 4, 4, 4, 5, 5, 7, 9];
    println!("{} {} {}", mean(&data), stdev(&data), stdev(&data).round_ties_even() as i64);
}
