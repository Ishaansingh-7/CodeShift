public class Main
{
    static long sumDigits(long n)
    {
        long total = 0;
        while (n > 0)
        {
            total += n % 10;
            n /= 10;
        }
        return total;
    }

    public static void main(String[] args)
    {
        System.out.println(sumDigits(4096));
    }
}
