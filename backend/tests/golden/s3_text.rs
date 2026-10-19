fn describe(s: &str) -> String {
    let t = s.trim().to_string();
    let first = t[0..1].to_uppercase();
    let rest = t[1..].to_lowercase();
    format!("{}{}", first, rest)
}

fn count(s: &str, c: char) -> i64 {
    let mut n = 0;
    for ch in s.chars() {
        if ch == c {
            n += 1;
        }
    }
    n
}

fn main() {
    let name = "  hELLO wORLD  ";
    let title = describe(name);
    println!("{} {} {} {}", title, count(&title, 'o'), title.find("World").map(|i| i as i64).unwrap_or(-1), title.replace("World", "There"));
    println!("{} {} {}", "abc" < "abd", "b" > "a", title.ends_with("rld"));
}
