public class Main
{
    static boolean isPrime(long n)
    {
        if (n < 2)
        {
            return false;
        }
        for (long i = 2; i * i <= n; i++)
        {
            if (n % i == 0)
            {
                return false;
            }
        }
        return true;
    }

    public static void main(String[] args)
    {
        System.out.println(isPrime(97));
    }
}
