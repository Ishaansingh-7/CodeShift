import java.util.ArrayList;
import java.util.List;

public class Main
{
    static ArrayList<Long> run(ArrayList<Long> ops)
    {
        ArrayList<Long> stack = new ArrayList<>();
        for (long x : ops)
        {
            if (x > 0)
            {
                stack.add(x);
            }
            else if (stack.size() > 0)
            {
                stack.remove(stack.size() - 1);
            }
        }
        return stack;
    }

    public static void main(String[] args)
    {
        System.out.println(run(new ArrayList<>(List.of(5L, 3L, 0L, 8L, 0L, 0L, 2L, 7L))));
    }
}
