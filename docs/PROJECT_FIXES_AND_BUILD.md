# Hadoop Studio — MapReduce fixes and rebuild

## What changed

- The reducer count selected in the UI is now passed to the Java MapReduce entry points and applied with `job.setNumReduceTasks(...)`.
- Each Java job accepts `[reducers]` as an optional third argument; valid values are 1–8, with 1 as the default.
- Output folder names are validated and include a microsecond timestamp plus a unique suffix to avoid collisions on rapid repeat submissions.
- HDFS input path validation rejects relative paths, traversal path components, backslashes, and control characters.
- The result viewer renders tab-separated Hadoop output in a searchable table and keeps the raw output available in a disclosure section.
- Result retrieval reports stderr/stdout details and a timeout message instead of returning an unhelpful `None` error.

## Important: rebuild the JAR

The existing `jars/mapreduce-jobs.jar` does **not** automatically update when Java source files change. Rebuild it after copying the updated project files.

From the WSL Ubuntu terminal:

```bash
cd /mnt/c/hadoop_proj
bash scripts/build-mapreduce.sh
```

If Hadoop is installed in a different directory:

```bash
HADOOP_HOME=/path/to/hadoop bash scripts/build-mapreduce.sh
```

The script compiles all three Java job classes against the Hadoop installation's own classpath and replaces only `jars/mapreduce-jobs.jar`. It does not touch HDFS data.

## Restart and smoke-test

1. Stop Flask with `Ctrl+C` in the PowerShell terminal where it is running.
2. In PowerShell:

   ```powershell
   cd C:\hadoop_proj
   .\.venv\Scripts\python.exe run.py
   ```

3. Open `http://127.0.0.1:5000/mapreduce/`.
4. Select **Word Count**, input `/user/chethan/sample.txt`, output name `wordcount_smoke`, and reducer count `1`.
5. Submit, wait for `FINISHED`, click **Fetch result**, and use the result filter to search for a known word.
6. Repeat with a different output name and reducer count `2` to verify the setting is accepted. For a tiny input, more reducers may create empty part files; that is normal Hadoop behavior.

## Safety notes

- Job output remains under `/user/chethan/phase5_test/`; input paths are not modified by MapReduce.
- Do not run `hdfs namenode -format` for these changes.
- The current Flask job registry is in memory. Job history shown by the app is lost when the Flask process restarts; HDFS output folders remain.
- This is a local development application. Do not expose Flask's debug server to an untrusted network.
