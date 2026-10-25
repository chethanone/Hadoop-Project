#!/usr/bin/env bash
set -e
# Hadoop installation path inside WSL Ubuntu
HADOOP_HOME=/home/chethan/hadoop-3.5.0
# Project root in WSL (mounted from Windows)
PROJECT_ROOT="/mnt/c/hadoop_proj"
SRC_DIR="$PROJECT_ROOT/src/mapreduce/java"
OUT_DIR="/tmp/hadoop_build"
# Clean previous build artifacts
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
# Get Hadoop classpath
CLASSPATH=$($HADOOP_HOME/bin/hadoop classpath)
# Compile Java sources with Java 17 target
javac -source 17 -target 17 -classpath "$CLASSPATH" -d "$OUT_DIR" "$SRC_DIR"/*.java
# Package compiled classes into a jar in the temp dir
jar -cvf "$OUT_DIR/mapreduce-jobs.jar" -C "$OUT_DIR" .
# Copy the JAR to the project jars directory
cp "$OUT_DIR/mapreduce-jobs.jar" "$PROJECT_ROOT/jars/"
echo "Compilation successful. JAR copied to $PROJECT_ROOT/jars/mapreduce-jobs.jar"
