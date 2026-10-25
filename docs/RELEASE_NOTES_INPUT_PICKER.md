# Input Picker and Random Sample Release

## Changes

- The MapReduce page can browse `/user/chethan/inputs` in place. Directory listing uses WebHDFS first, with a short-timeout CLI fallback. Files can be selected directly into the input-path field.
- Every Generate Random Samples click creates fresh Word Count text, randomized 2×2 matrix elements, and weather rows matching the bundled `WeatherAnalysis` CSV schema. Each run uploads into a unique HDFS folder and never overwrites earlier samples. Temporary local generated files are removed after upload.
- The HDFS file manager no longer runs a blocking `hdfs dfs -mkdir` command on each page navigation; listing remains read-only and uses the existing WebHDFS-first adapter.
- Input preview uses the adapter's streamed WebHDFS preview with a 12,000-byte cap where WebHDFS is available.
- Matrix Multiplication is forced to one reducer in both UI and submission validation.
- Removed duplicate result-panel elements and duplicate HTML IDs from the MapReduce page.
- Updated static asset cache versions so the browser fetches the new UI.

## Safety and scope

- No HDFS formatting, deletion, renaming, or overwrite is performed by sample generation.
- Existing user files and previous demo folders are preserved.
- The input picker is restricted to `/user/chethan/inputs`.

## Validation performed in this build environment

- Python syntax compilation passed for changed Python modules.
- JavaScript syntax check passed with Node.js.
- The MapReduce template has unique IDs for result heading, summary, visualization, raw output, and raw-output toggle.
- Full live Windows + WSL + Hadoop integration was not available here; test the sample-generation and picker endpoints in the user's environment after extracting.
