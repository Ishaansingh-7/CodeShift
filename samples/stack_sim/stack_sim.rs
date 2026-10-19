fn run(ops: &[i64]) -> Vec<i64> {
    let mut stack = Vec::new();
    for &x in ops.iter() {
        if x > 0 {
            stack.push(x);
        } else if stack.len() > 0 {
            stack.pop().unwrap();
        }
    }
    stack
}

fn main() {
    println!("{:?}", run(&[5, 3, 0, 8, 0, 0, 2, 7]));
}
