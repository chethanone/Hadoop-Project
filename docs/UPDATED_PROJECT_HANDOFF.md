# Hadoop Studio — Updated source handoff

This update preserves the existing Flask application and focuses on MapReduce correctness and output usability.

## Updated files
- `src/app/routes/mapreduce.py`: safer path/name validation, collision-resistant output paths, reducer argument forwarding, improved output retrieval errors.
- `src/app/templates/mapreduce.html`: result explorer layout.
- `src/app/static/js/mapreduce.js`: searchable table view for tab-separated output, with raw output still available.
- `src/app/static/css/custom.css`: responsive styling for the output explorer.
- `src/mapreduce/java/*.java`: validate and apply the selected reducer count.
- `scripts/build-mapreduce.sh`: rebuild the Java JAR using the Hadoop installation's classpath.
- `docs/PROJECT_FIXES_AND_BUILD.md`: build and smoke-test instructions.

## Apply the update
Extract this ZIP into `C:\hadoop_proj` and allow updated files to replace matching source files. Do not delete your project folder or HDFS data.

Then rebuild the JAR from WSL Ubuntu:
```bash
cd /mnt/c/hadoop_proj
bash scripts/build-mapreduce.sh
```

Restart Flask from PowerShell:
```powershell
cd C:\hadoop_proj
.\.venv\Scripts\python.exe run.py
```

Open `http://127.0.0.1:5000/`.

## Validation performed for this source bundle
- Python source syntax parsing: passed.
- MapReduce JavaScript syntax check (`node --check`): passed.
- Full pytest execution could not be completed in the review environment because Flask is not installed in that environment. Run the tests in your project virtual environment after applying the update.
- The Java JAR is not rebuilt in this environment because Hadoop's Java classpath is available in your WSL installation, not here. The included script performs that build in WSL without modifying HDFS.
