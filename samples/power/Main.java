public class Main
{
    static long power(long b, long e)
    {
        if (e == 0)
        {
            return 1;
        }
        long half = power(b, e / 2);
        if (e % 2 == 0)
        {
            return half * half;
        }
        return half * half * b;
    }

    public static void main(String[] args)
    {
        System.out.println(power(2, 10));
    }
}
