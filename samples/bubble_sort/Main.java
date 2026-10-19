import java.util.Arrays;

public class Main
{
    static void bubble(long[] xs)
    {
        for (int i = 0; i < xs.length; i++)
        {
            for (int j = 0; j < xs.length - 1 - i; j++)
            {
                if (xs[j] > xs[j + 1])
                {
                    long t = xs[j];
                    xs[j] = xs[j + 1];
                    xs[j + 1] = t;
                }
            }
        }
    }

    public static void main(String[] args)
    {
        long[] xs = {5, 1, 4, 2, 8};
        bubble(xs);
        System.out.println(Arrays.toString(xs));
    }
}
