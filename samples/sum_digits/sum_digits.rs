fn sum_digits(mut n: i64) -> i64 {
    let mut total = 0;
    while n > 0 {
        total += n % 10;
        n /= 10;
    }
    total
}

fn main() {
    println!("{}", sum_digits(4096));
}
