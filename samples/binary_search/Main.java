public class Main
{
    static int search(long[] xs, long t)
    {
        int lo = 0, hi = xs.length - 1;
        while (lo <= hi)
        {
            int mid = (lo + hi) / 2;
            if (xs[mid] == t)
            {
                return mid;
            }
            if (xs[mid] < t)
            {
                lo = mid + 1;
            }
            else
            {
                hi = mid - 1;
            }
        }
        return -1;
    }

    public static void main(String[] args)
    {
        System.out.println(search(new long[]{1, 3, 5, 7, 9, 11}, 7));
    }
}
