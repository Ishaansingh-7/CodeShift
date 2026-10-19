public class Main
{
    static long fib(int n)
    {
        long a = 0, b = 1;
        for (int i = 0; i < n; i++)
        {
            long t = b;
            b = a + b;
            a = t;
        }
        return a;
    }

    public static void main(String[] args)
    {
        System.out.println(fib(10));
    }
}
