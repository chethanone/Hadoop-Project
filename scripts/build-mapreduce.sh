#!/usr/bin/env bash
set -euo pipefail

# Run from WSL Ubuntu, with Hadoop installed at ~/hadoop-3.5.0 by default.
PROJECT_DIR="${PROJECT_DIR:-/mnt/c/hadoop_proj}"
HADOOP_HOME="${HADOOP_HOME:-$HOME/hadoop-3.5.0}"
JAVA_DIR="$PROJECT_DIR/src/mapreduce/java"
BUILD_DIR="$PROJECT_DIR/.build/mapreduce-classes"
JAR_DIR="$PROJECT_DIR/jars"
JAR_PATH="$JAR_DIR/mapreduce-jobs.jar"

if [[ ! -x "$HADOOP_HOME/bin/hadoop" ]]; then
  echo "ERROR: Hadoop CLI not found at $HADOOP_HOME/bin/hadoop" >&2
  echo "Set HADOOP_HOME to your Hadoop installation directory." >&2
  exit 1
fi
if [[ ! -d "$JAVA_DIR" ]]; then
  echo "ERROR: Java source directory not found: $JAVA_DIR" >&2
  exit 1
fi

mkdir -p "$BUILD_DIR" "$JAR_DIR"
rm -rf "$BUILD_DIR"/*
CLASSPATH="$("$HADOOP_HOME/bin/hadoop" classpath)"
javac -encoding UTF-8 -cp "$CLASSPATH" -d "$BUILD_DIR" "$JAVA_DIR"/*.java
jar cf "$JAR_PATH" -C "$BUILD_DIR" .
echo "Built MapReduce jar: $JAR_PATH"
echo "Classes included:"
jar tf "$JAR_PATH" | grep -E '^(WordCount|MatrixMultiplication|WeatherAnalysis)(\$.*)?\.class$' || true
