# Hadoop Studio — Final User Guide

## What the application does
- **HDFS File Manager:** browse and manage files in HDFS.
- **MapReduce Lab:** submit Java MapReduce jobs through Hadoop 3.5.0 in WSL, inspect actual job logs and YARN progress where the ResourceManager reports it, and read result files from HDFS.

## Input formats
### Word Count (`datasets/wordcount.txt`)
UTF-8 text. The current Java implementation tokenizes on whitespace; it does not normalize case or remove punctuation.

### Matrix Multiplication (`datasets/matrix.txt`)
One matrix element per line: `M row column value` for matrix A and `N row column value` for matrix B. Indices are zero-based. The current educational implementation sends all elements to one reducer so the reducer can calculate the product correctly for small matrices. This is intentionally not a scalable matrix multiplication strategy for large matrices.

### Weather Analysis (`datasets/weather.csv`)
Comma-separated fields where column 1 is station ID, column 2 is date, and column 3 is numeric temperature. Header rows beginning with `station` and invalid temperature rows are skipped. Results contain station ID, valid row count, and average temperature.

## Run a job
1. Start HDFS and YARN in Ubuntu/WSL.
2. Upload the relevant sample dataset through HDFS File Manager into `/user/chethan/inputs/` (or use an existing HDFS path).
3. Select the matching algorithm and enter that HDFS input path.
4. Set an output label and reducer count. Matrix multiplication uses one reducer by design for correctness on small examples; its Java driver overrides the requested reducer count.
5. Submit. The output is written to a unique folder under `/user/chethan/outputs/`.
6. When the job finishes successfully, select **Load visualized results**. The raw output remains available for verification.

## Interpreting the monitor
- Job state and logs are returned by the actual background Hadoop process.
- The percentage is displayed only when YARN provides a progress value.
- Workflow stage labels are explanatory indicators inferred from available logs/status; they are not per-task counters. Do not present them as detailed task telemetry.
- A job is successful only when the Hadoop process exits with code zero. Always inspect logs if it fails.

## Safety
- Existing HDFS content is not moved or deleted by this update.
- New job outputs use unique names under `/user/chethan/outputs/`.
- Do not run `hdfs namenode -format` as part of normal startup or testing.
