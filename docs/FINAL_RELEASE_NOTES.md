# Final release notes

This release consolidates the professional UI and HDFS input/output comparison updates with the working MapReduce JAR and sample datasets.

## Reliability and performance adjustments

- The input preview reads at most 12,001 bytes from HDFS and displays at most 12,000 characters. It no longer buffers the entire input dataset merely to display a preview.
- Input preview errors are returned separately from reducer output errors.
- Result filtering is shown only for result tables with more than 10 rows; small weather and matrix results remain uncluttered.
- The build script lists nested Java job classes correctly after creating the JAR.
- Existing HDFS files are not formatted, deleted, or overwritten by these project files. Sample inputs are uploaded into a unique demo folder.

## Validation performed for this archive

- Python source syntax checked with `py_compile`.
- Browser JavaScript syntax checked with `node --check`.
- Java job classes confirmed present in the packaged JAR.
- ZIP archive integrity checked after packaging.

The live Hadoop/YARN integration suite requires the user's own Windows + WSL Ubuntu Hadoop environment and was not executable in this packaging environment. Run the included tests in the project environment before relying on live integration behavior.
