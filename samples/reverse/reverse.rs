fn reverse(s: &str) -> String {
    let mut out = String::new();
    for ch in s.chars() {
        out.insert(0, ch);
    }
    out
}

fn main() {
    println!("{}", reverse("CodeShift"));
}
