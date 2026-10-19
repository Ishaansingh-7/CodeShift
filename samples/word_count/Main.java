import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.TreeSet;

public class Main
{
    static ArrayList<String> csSplitWs(String s)
    {
        String t = s.strip();
        return t.isEmpty() ? new ArrayList<>() : new ArrayList<>(List.of(t.split("\\s+")));
    }

    static String wordCount(String text)
    {
        LinkedHashMap<String, Long> counts = new LinkedHashMap<>();
        for (String w : csSplitWs(text))
        {
            counts.merge(w, 1L, Long::sum);
        }
        String best = "";
        for (String w : new ArrayList<>(new TreeSet<>(counts.keySet())))
        {
            if (best.equals("") || counts.get(w) > counts.get(best) || (long)counts.get(w) == counts.get(best) && w.compareTo(best) < 0)
            {
                best = w;
            }
        }
        return best + " " + Long.toString(counts.get(best));
    }

    public static void main(String[] args)
    {
        System.out.println(wordCount("the cat and the hat and the bat"));
    }
}
