function reverse(s) {
  let out = "";
  for (const ch of s) {
    out = ch + out;
  }
  return out;
}

console.log(reverse("CodeShift"));
