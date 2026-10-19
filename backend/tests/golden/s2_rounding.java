public class Main
{
    static double csRoundAway(double x)
    {
        return Math.signum(x) * Math.floor(Math.abs(x) + 0.5);
    }

    public static void main(String[] args)
    {
        System.out.println(csRoundAway(2.5) + " " + csRoundAway(-2.5) + " " + Math.round(2.5) + " " + Math.round(-2.5) + " " + (long)Math.rint(2.5));
    }
}
