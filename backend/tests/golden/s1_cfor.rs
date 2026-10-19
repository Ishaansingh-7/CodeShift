fn squares(n: i64) -> i64 {
    let mut total = 0;
    let mut i = 0;
    loop {
        i += 1;
        if i * i > n {
            break;
        }
        if i % 2 == 0 {
            continue;
        }
        total += i * i;
    }
    total
}

fn main() {
    println!("{}", squares(50));
}
