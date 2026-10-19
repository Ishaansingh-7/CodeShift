fn bubble(xs: &mut Vec<i64>) {
    for i in 0..xs.len() {
        for j in 0..xs.len() - 1 - i {
            if xs[j] > xs[j + 1] {
                xs.swap(j, j + 1);
            }
        }
    }
}

fn main() {
    let mut xs = vec![5, 1, 4, 2, 8];
    bubble(&mut xs);
    println!("{:?}", xs);
}
