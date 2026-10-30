fn greet(name: &'static str) -> String {
    format!("hi {}", name)
}

fn main() {
    let x: i64 = 11;
    let y: i64 = 6;
    println!("{} {} {}", x & y, x | y, x ^ y);
    println!("{} {} {}", x << 3, 200 >> 2, !x);
    let mut flags: i64 = 0;
    flags |= 4;
    flags ^= 1;
    flags &= !4;
    flags <<= 2;
    println!("{} {}", flags, 1i64 << 40);
    println!("{}", greet("bits"));
}
