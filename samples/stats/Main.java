public class Main
{
    static double mean(long[] xs)
    {
        long total = 0;
        for (long x : xs)
        {
            total += x;
        }
        return (double)total / (double)xs.length;
    }

    static double stdev(long[] xs)
    {
        double m = mean(xs);
        double s = 0.0;
        for (long x : xs)
        {
            s += ((double)x - m) * ((double)x - m);
        }
        return Math.sqrt(s / (double)xs.length);
    }

    public static void main(String[] args)
    {
        long[] data = {2, 4, 4, 4, 5, 5, 7, 9};
        System.out.println(mean(data) + " " + stdev(data) + " " + (long)Math.rint(stdev(data)));
    }
}
