public class Main
{
    static long gcd(long a, long b)
    {
        while (b != 0)
        {
            long t = b;
            b = a % b;
            a = t;
        }
        return a;
    }

    public static void main(String[] args)
    {
        System.out.println(gcd(48, 18));
    }
}
