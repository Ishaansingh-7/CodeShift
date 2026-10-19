fn mean(a: i64, b: i64) -> f64 {
    (a + b) as f64 / 2.0
}

fn area(r: f64) -> f64 {
    3.25 * r * r
}

fn scale(x: f64, k: i64) -> f64 {
    let mut y = x * k as f64;
    y += 0.5;
    y /= 2.0;
    y
}

fn halve(n: i64) -> f64 {
    n as f64 / 2.0
}

fn main() {
    let x = 1.5;
    let y = x * 4.0 - 0.25;
    let n: i64 = 7;
    let z = n as f64 / 2.0;
    let w = y as i64;
    let v = n as f64 + x;
    let tiny = 2.5e-3;
    println!("{} {} {} {}", mean(3, 4), area(2.0), scale(1.5, 3), halve(9));
    println!("{} {} {} {} {} {}", y, z, w, v, -x, tiny * 4.0);
    if y > n as f64 {
        println!("big");
    } else {
        println!("small");
    }
}
