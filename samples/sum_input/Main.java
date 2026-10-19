import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class Main
{
    static BufferedReader csIn = new BufferedReader(new InputStreamReader(System.in));

    static String csReadLine()
    {
        try
        {
            String s = csIn.readLine();
            return s == null ? "" : s;
        }
        catch (IOException e)
        {
            return "";
        }
    }

    static ArrayList<String> csSplitWs(String s)
    {
        String t = s.strip();
        return t.isEmpty() ? new ArrayList<>() : new ArrayList<>(List.of(t.split("\\s+")));
    }

    static ArrayList<Long> csInts(String s)
    {
        ArrayList<Long> r = new ArrayList<>();
        for (String w : csSplitWs(s))
        {
            r.add(Long.parseLong(w));
        }
        return r;
    }

    static long total(ArrayList<Long> nums)
    {
        long s = 0;
        for (long x : nums)
        {
            s += x;
        }
        return s;
    }

    public static void main(String[] args)
    {
        String name = csReadLine();
        ArrayList<Long> nums = csInts(csReadLine());
        System.out.println("Hello " + name);
        System.out.println("sum " + total(nums) + " max " + Collections.max(nums));
    }
}
