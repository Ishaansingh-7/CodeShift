fn fact(n: i64) -> i64 {
    if n <= 1 {
        return 1;
    }
    n * fact(n - 1)
}

fn main() {
    println!("{}", fact(10));
}
