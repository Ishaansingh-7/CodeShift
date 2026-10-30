const LIMIT = 10;

function power(b, e = 2) {
    let r = 1;
    for (let i = 0; i < e; i++) {
        r *= b;
    }
    return r;
}

function scaled(n) {
    return n * LIMIT;
}

function name(n) {
    switch (n) {
        case 1:
            return "one";
        case 2:
            return "two";
        default:
            return "many";
    }
}

const a = 4;
const b = 9;
const big = a > b ? a : b;
let i = 0;
do {
    i += 3;
} while (i < 10);
const label = "n=" + i;
console.log(`${a} + ${b} = ${a + b}, big=${big}`);
console.log(power(5), power(2, 10), scaled(3), name(2), label);
