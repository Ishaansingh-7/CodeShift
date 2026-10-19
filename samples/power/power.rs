fn power(b: i64, e: i64) -> i64 {
    if e == 0 {
        return 1;
    }
    let half = power(b, e / 2);
    if e % 2 == 0 {
        return half * half;
    }
    half * half * b
}

fn main() {
    println!("{}", power(2, 10));
}
