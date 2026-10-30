public class Main {
    static int digitSum(String s) {
        int total = 0;
        for (int i = 0; i < s.length(); i++) {
            total += s.charAt(i) - '0';
        }
        return total;
    }

    public static void main(String[] args) {
        long x = 11, y = 6;
        System.out.println((x & y) + " " + (x | y) + " " + (x ^ y));
        System.out.println((x << 3) + " " + (200 >> 2) + " " + (~x));
        long flags = 0;
        flags |= 4;
        flags ^= 1;
        flags &= ~4;
        flags <<= 2;
        System.out.println(flags + " " + (1L << 40));
        String out = "";
        for (char c = 'a'; c <= 'e'; c++) {
            out += c;
        }
        for (int i = 0; i < 3; i++) {
            out += (char) ('x' + i);
        }
        System.out.println(out);
        char d = 'A';
        d += 2;
        d++;
        System.out.println(d + " " + ('z' - 'a') + " " + digitSum("4096"));
    }
}
