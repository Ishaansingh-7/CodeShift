public class Main
{
    static String reverse(String s)
    {
        StringBuilder out = new StringBuilder();
        for (char ch : s.toCharArray())
        {
            out.insert(0, ch);
        }
        return out.toString();
    }

    public static void main(String[] args)
    {
        System.out.println(reverse("CodeShift"));
    }
}
