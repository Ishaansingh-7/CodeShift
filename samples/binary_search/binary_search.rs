fn search(xs: &[i64], t: i64) -> i64 {
    let (mut lo, mut hi) = (0i64, xs.len() as i64 - 1);
    while lo <= hi {
        let mid = (lo + hi) / 2;
        if xs[mid as usize] == t {
            return mid;
        }
        if xs[mid as usize] < t {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    -1
}

fn main() {
    println!("{}", search(&[1, 3, 5, 7, 9, 11], 7));
}
