import java.util.Arrays;

public class Main
{
    static final int LIMIT = 21;
    static final double RATE = 2;

    static long total(int[] a)
    {
        long s = 0;
        for (int x : a)
        {
            s += x;
        }
        return s;
    }

    public static void main(String[] args)
    {
        int[] a = new int[4];
        a[2] = 7;
        int[][] g = new int[2][3];
        g[1][2] = 5;
        int[][] h = {{1, 2}, {3, 4}};
        String[] names = {"ann", "bob"};
        String[] parts = "a b c".split(" ");
        int[] b = {5, 2, 9};
        Arrays.sort(b);
        int n = Integer.parseInt("42");
        int d = 2;
        String label = d > 1 ? "big" : "small";
        switch (d)
        {
            case 1:
                System.out.println("one");
                break;
            default:
                System.out.println("other");
        }
        int i = 0;
        do
        {
            i += 3;
        } while (i < 10);
        System.out.printf("%d %d %d %s %d %d %d %s %d%n", a[2], g[1][2], h[1][0], names[1], parts.length, b[0], n, label, i);
        System.out.printf("%.2f %d%n", RATE * 1.5, LIMIT * 2);
        System.out.println(Integer.MAX_VALUE + " " + total(b));
    }
}
