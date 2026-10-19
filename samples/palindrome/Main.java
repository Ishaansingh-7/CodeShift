public class Main
{
    static String clean(String s)
    {
        String out = "";
        for (char ch : s.toLowerCase().toCharArray())
        {
            if (Character.isLetter(ch))
            {
                out += ch;
            }
        }
        return out;
    }

    static boolean isPalindrome(String s)
    {
        String t = clean(s);
        int i = 0;
        for (int j = t.length() - 1; i < j; j--)
        {
            if (t.charAt(i) != t.charAt(j))
            {
                return false;
            }
            i += 1;
        }
        return true;
    }

    public static void main(String[] args)
    {
        System.out.println(isPalindrome("Never odd or even"));
    }
}
