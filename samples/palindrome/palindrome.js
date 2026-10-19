function csIsAlpha(c) {
  return (c >= "a" && c <= "z") || (c >= "A" && c <= "Z");
}

function clean(s) {
  let out = "";
  for (const ch of s.toLowerCase()) {
    if (csIsAlpha(ch)) {
      out += ch;
    }
  }
  return out;
}

function isPalindrome(s) {
  const t = clean(s);
  let i = 0;
  for (let j = t.length - 1; i < j; j--) {
    if (t[i] !== t[j]) {
      return false;
    }
    i += 1;
  }
  return true;
}

console.log(isPalindrome("Never odd or even"));
