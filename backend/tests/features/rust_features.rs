const LIMIT: i64 = 21;

fn grade(n: i64) -> i64 {
    match n {
        90..=100 => 1,
        50..=89 => 2,
        _ => 3,
    }
}

fn biggest(a: i64, b: i64) -> i64 {
    if a > b { a } else { b }
}

fn describe(d: i64) {
    match d {
        1 => println!("one"),
        2 | 3 => {
            println!("few");
        }
        _ => println!("many"),
    }
}

fn main() {
    let xs = vec![1, 2, 3];
    let s: i64 = xs.iter().sum();
    let n: i64 = "42".parse().unwrap();
    let m = "7".parse::<i64>().unwrap();
    let label = if n > 40 { "big" } else { "small" };
    let code = match m {
        7 => 70,
        _ => 0,
    };
    describe(2);
    println!("{} {} {} {} {} {} {} {}", grade(75), biggest(3, 9), s, n + m, label, code, LIMIT * 2, i32::MAX);
}
