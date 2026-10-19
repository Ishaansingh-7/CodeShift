public class Main
{
    static String describe(String s)
    {
        String t = s.trim();
        String first = t.substring(0, 1).toUpperCase();
        String rest = t.substring(1).toLowerCase();
        return first + rest;
    }

    static long count(String s, char c)
    {
        long n = 0;
        for (char ch : s.toCharArray())
        {
            if (ch == c)
            {
                n++;
            }
        }
        return n;
    }

    public static void main(String[] args)
    {
        String name = "  hELLO wORLD  ";
        String title = describe(name);
        System.out.println(title + " " + count(title, 'o') + " " + title.indexOf("World") + " " + title.replace("World", "There"));
        System.out.println(("abc".compareTo("abd") < 0) + " " + ("b".compareTo("a") > 0) + " " + title.endsWith("rld"));
    }
}
