import java.util.ArrayList;
import java.util.Collections;

public class Main
{
    static <T> ArrayList<ArrayList<T>> csGrid(long r, long c, T v)
    {
        ArrayList<ArrayList<T>> g = new ArrayList<>();
        for (long i = 0; i < r; i++)
        {
            g.add(new ArrayList<>(Collections.nCopies((int)c, v)));
        }
        return g;
    }

    static ArrayList<ArrayList<Long>> makeGrid(int rows, int cols)
    {
        ArrayList<ArrayList<Long>> grid = csGrid(rows, cols, 0L);
        for (int i = 0; i < rows; i++)
        {
            for (int j = 0; j < cols; j++)
            {
                grid.get(i).set(j, ((long)i + 1) * (j + 1));
            }
        }
        return grid;
    }

    static long matrixSum(long rows, long cols)
    {
        ArrayList<ArrayList<Long>> grid = makeGrid((int)rows, (int)cols);
        long total = 0;
        for (ArrayList<Long> row : grid)
        {
            for (long v : row)
            {
                total += v;
            }
        }
        return total;
    }

    public static void main(String[] args)
    {
        System.out.println(matrixSum(3, 4));
    }
}
