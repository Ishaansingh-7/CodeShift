fn cs_round_js(x: f64) -> f64 {
    (x + 0.5).floor()
}

fn main() {
    println!("{} {} {} {} {}", 2.5_f64.round(), (-2.5_f64).round(), cs_round_js(2.5), cs_round_js(-2.5), 2.5_f64.round_ties_even() as i64);
}
