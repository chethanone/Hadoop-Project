# Hadoop Studio responsiveness improvements

## Changes in this update

- System Health diagnostics now run independent WSL/HTTP/HDFS probes concurrently instead of serially waiting for every probe. Results and remediation checks remain the same.
- Flask serves same-origin static CSS/JavaScript with a one-day cache lifetime to reduce repeated static asset revalidation.
- Removed the external Google Fonts stylesheet so page rendering does not depend on the Google Fonts endpoints; the existing CSS font fallbacks are used instead.

## Safety and correctness

- No HDFS commands that mutate data were added.
- No Hadoop daemon/configuration changes were made.
- HDFS authorization/path checks and protected-path controls are unchanged.
- This change does not cache HDFS listings or MapReduce results, so file operations and job outputs remain current.

## Apply

Extract this archive over the existing `C:\hadoop_proj` project, preserving existing files not present in the archive. Restart Flask with:

```powershell
cd C:\hadoop_proj
.\.venv\Scripts\python.exe run.py
```

Hard-refresh the browser once (`Ctrl+F5`) so it picks up the new page assets.

## Verification limitation

Python compile checks passed for the updated source. The full pytest suite could not run in the review environment because Flask is not installed there. Verify locally with the project's Windows virtual environment before relying on the update.
