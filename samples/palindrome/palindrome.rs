fn clean(s: &str) -> String {
    let mut out = String::new();
    for ch in s.to_lowercase().chars() {
        if ch.is_ascii_alphabetic() {
            out.push(ch);
        }
    }
    out
}

fn is_palindrome(s: &str) -> bool {
    let t = clean(s);
    let mut i = 0i64;
    let mut j = t.len() as i64 - 1;
    while i < j {
        if t.as_bytes()[i as usize] as char != t.as_bytes()[j as usize] as char {
            return false;
        }
        i += 1;
        j -= 1;
    }
    true
}

fn main() {
    println!("{}", is_palindrome("Never odd or even"));
}
