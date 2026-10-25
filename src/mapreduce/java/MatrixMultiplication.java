import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.Reducer;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import java.io.IOException;
import java.util.*;

/** Matrix multiplication demo. Input records: M row col value OR N row col value (zero-based indices). */
public class MatrixMultiplication {
    public static class MatrixMapper extends Mapper<LongWritable, Text, Text, Text> {
        private static final Text MATRIX_KEY = new Text("MATRIX");
        private final Text out = new Text();
        @Override protected void map(LongWritable offset, Text line, Context context) throws IOException, InterruptedException {
            String s = line.toString().trim();
            if (s.isEmpty() || s.startsWith("#")) return;
            String[] p = s.split("[\\s,]+", -1);
            if (p.length != 4 || !(p[0].equals("M") || p[0].equals("N"))) return;
            try {
                int row = Integer.parseInt(p[1]), col = Integer.parseInt(p[2]);
                double value = Double.parseDouble(p[3]);
                if (row < 0 || col < 0 || !Double.isFinite(value)) return;
                out.set(p[0] + "," + row + "," + col + "," + value);
                context.write(MATRIX_KEY, out);
            } catch (NumberFormatException ignored) { /* skip malformed input row */ }
        }
    }
    public static class MatrixReducer extends Reducer<Text, Text, Text, Text> {
        @Override protected void reduce(Text key, Iterable<Text> values, Context context) throws IOException, InterruptedException {
            Map<Integer, Map<Integer, Double>> a = new HashMap<>(), b = new HashMap<>();
            for (Text value : values) {
                String[] p = value.toString().split(",");
                if (p.length != 4) continue;
                try {
                    Map<Integer, Map<Integer, Double>> target = p[0].equals("M") ? a : p[0].equals("N") ? b : null;
                    if (target == null) continue;
                    int r = Integer.parseInt(p[1]), c = Integer.parseInt(p[2]);
                    double v = Double.parseDouble(p[3]);
                    target.computeIfAbsent(r, unused -> new HashMap<>()).put(c, v);
                } catch (NumberFormatException ignored) { }
            }
            TreeSet<Integer> aRows = new TreeSet<>(a.keySet());
            TreeSet<Integer> bCols = new TreeSet<>();
            for (Map<Integer, Double> row : b.values()) bCols.addAll(row.keySet());
            for (int i : aRows) for (int k : bCols) {
                double sum = 0.0;
                Map<Integer, Double> aRow = a.get(i);
                for (Map.Entry<Integer, Double> e : aRow.entrySet()) {
                    Map<Integer, Double> bRow = b.get(e.getKey());
                    if (bRow != null && bRow.containsKey(k)) sum += e.getValue() * bRow.get(k);
                }
                context.write(new Text(i + "," + k), new Text(Double.toString(sum)));
            }
        }
    }
    public static void main(String[] args) throws Exception {
        if (args.length < 2 || args.length > 3) { System.err.println("Usage: MatrixMultiplication <input> <output> [reducers]"); System.exit(2); }
        Configuration conf = new Configuration(); Job job = Job.getInstance(conf, "matrix multiplication");
        job.setJarByClass(MatrixMultiplication.class); job.setMapperClass(MatrixMapper.class); job.setReducerClass(MatrixReducer.class);
        job.setMapOutputKeyClass(Text.class); job.setMapOutputValueClass(Text.class); job.setOutputKeyClass(Text.class); job.setOutputValueClass(Text.class);
        // All matrix elements are grouped to one reducer for a correct, easy-to-demonstrate small matrix product.
        job.setNumReduceTasks(1);
        FileInputFormat.addInputPath(job, new Path(args[0])); FileOutputFormat.setOutputPath(job, new Path(args[1]));
        System.exit(job.waitForCompletion(true) ? 0 : 1);
    }
}
