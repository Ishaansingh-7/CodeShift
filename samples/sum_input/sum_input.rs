fn cs_read_line() -> String {
    let mut s = String::new();
    std::io::stdin().read_line(&mut s).unwrap();
    s.trim_end_matches(['\r', '\n']).to_string()
}

fn total(nums: &[i64]) -> i64 {
    let mut s = 0;
    for &x in nums.iter() {
        s += x;
    }
    s
}

fn main() {
    let name = cs_read_line();
    let nums = cs_read_line().split_whitespace().map(|t| t.parse::<i64>().unwrap()).collect::<Vec<i64>>();
    println!("Hello {}", name);
    println!("sum {} max {}", total(&nums), *nums.iter().max().unwrap());
}
