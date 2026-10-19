use std::collections::BTreeMap;

fn word_count(text: &str) -> String {
    let mut counts: BTreeMap<String, i64> = BTreeMap::new();
    for w in text.split_whitespace().map(String::from).collect::<Vec<String>>().iter().cloned() {
        *counts.entry(w.clone()).or_insert(0) += 1;
    }
    let mut best = String::new();
    for w in counts.keys().cloned() {
        if best == "" || counts[&w] > counts[&best] || counts[&w] == counts[&best] && w < best {
            best = w.clone();
        }
    }
    format!("{} {}", best, counts[&best].to_string())
}

fn main() {
    println!("{}", word_count("the cat and the hat and the bat"));
}
