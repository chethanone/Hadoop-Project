import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.DoubleWritable;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.Reducer;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;

import java.io.IOException;
import java.util.Locale;

/**
 * Summarizes the bundled weather CSV by station.
 * Expected columns: Year,Month,StationID,MaxTemp,MinTemp,Precipitation
 * The reported average is the mean of (MaxTemp + MinTemp) / 2 for each valid row.
 */
public class WeatherAnalysis {
    public static class WeatherMapper extends Mapper<LongWritable, Text, Text, DoubleWritable> {
        private final Text station = new Text();
        private final DoubleWritable recordAverage = new DoubleWritable();

        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {
            String line = value.toString().trim();
            if (line.isEmpty() || line.toLowerCase(Locale.ROOT).startsWith("year,")) return;

            String[] parts = line.split(",", -1);
            if (parts.length < 6) {
                context.getCounter("WeatherAnalysis", "INVALID_ROWS").increment(1);
                return;
            }

            try {
                String stationId = parts[2].trim();
                double maxTemp = Double.parseDouble(parts[3].trim());
                double minTemp = Double.parseDouble(parts[4].trim());
                if (stationId.isEmpty() || !Double.isFinite(maxTemp) || !Double.isFinite(minTemp)) {
                    context.getCounter("WeatherAnalysis", "INVALID_ROWS").increment(1);
                    return;
                }
                station.set(stationId);
                recordAverage.set((maxTemp + minTemp) / 2.0);
                context.write(station, recordAverage);
                context.getCounter("WeatherAnalysis", "VALID_ROWS").increment(1);
            } catch (NumberFormatException e) {
                context.getCounter("WeatherAnalysis", "INVALID_ROWS").increment(1);
            }
        }
    }

    public static class AvgReducer extends Reducer<Text, DoubleWritable, Text, Text> {
        @Override
        protected void reduce(Text key, Iterable<DoubleWritable> values, Context context)
                throws IOException, InterruptedException {
            double sum = 0.0;
            int count = 0;
            for (DoubleWritable value : values) {
                sum += value.get();
                count++;
            }
            if (count == 0) return;
            String result = String.format(Locale.ROOT, "%d\t%.2f", count, sum / count);
            context.write(key, new Text(result));
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2 || args.length > 3) {
            System.err.println("Usage: WeatherAnalysis <input> <output> [reducers]");
            System.exit(2);
        }
        int reducers = args.length == 3 ? Integer.parseInt(args[2]) : 1;
        if (reducers < 1 || reducers > 8) throw new IllegalArgumentException("Reducers must be between 1 and 8");

        Configuration conf = new Configuration();
        Job job = Job.getInstance(conf, "weather analysis by station");
        job.setJarByClass(WeatherAnalysis.class);
        job.setMapperClass(WeatherMapper.class);
        job.setReducerClass(AvgReducer.class);
        job.setMapOutputKeyClass(Text.class);
        job.setMapOutputValueClass(DoubleWritable.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);
        job.setNumReduceTasks(reducers);
        FileInputFormat.addInputPath(job, new Path(args[0]));
        FileOutputFormat.setOutputPath(job, new Path(args[1]));
        System.exit(job.waitForCompletion(true) ? 0 : 1);
    }
}
