# Hadoop File Management and MapReduce Visualization System

A web-based interface for working with a Hadoop cluster running in Ubuntu under WSL2 on Windows. The project combines a Flask backend, a Bootstrap 5 dark-themed UI, HDFS file-management workflows, and three Java MapReduce jobs.

## Table of Contents
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Using the Application](#using-the-application)
- [MapReduce Jobs](#mapreduce-jobs)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Safety Notes](#safety-notes)

## Features

- **HDFS File Manager:** Browse HDFS files and directories and use supported file-management operations with path restrictions and safety guardrails.
- **MapReduce Lab:** Submit jobs, monitor their status, inspect available logs, and view or download results.
- **Dashboard:** View HDFS storage information and recent job statuses when Hadoop services are reachable.
- **Diagnostics:** Check connectivity and inspect diagnostic information to help troubleshoot configuration problems.
- **Dark-themed web UI:** Flask templates, Bootstrap 5, CSS, and JavaScript provide dedicated dashboard, file manager, diagnostics, and MapReduce pages.

## Technology Stack

| Area | Technologies |
| --- | --- |
| Backend | Python, Flask |
| Frontend | HTML, Bootstrap 5, CSS, JavaScript |
| Distributed storage | Hadoop Distributed File System (HDFS) |
| Resource management | YARN |
| Batch processing | Java MapReduce |
| Development environment | Windows, Ubuntu on WSL2 |
| Tests | pytest |

## Project Structure

```text
hadoop_proj/
├── run.py
├── requirements.txt
├── compile_mapreduce.sh
├── scripts/
│   └── build-mapreduce.sh
├── jars/
│   └── mapreduce-jobs.jar
├── datasets/
│   ├── wordcount.txt
│   ├── matrix.txt
│   └── weather.csv
├── docs/
├── src/
│   ├── app/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── static/
│   │   └── templates/
│   └── mapreduce/
│       └── java/
│           ├── WordCount.java
│           ├── MatrixMultiplication.java
│           └── WeatherAnalysis.java
└── tests/
```

## Prerequisites

- Windows 10/11 with WSL2 enabled.
- An Ubuntu distribution installed in WSL2.
- Hadoop 3.5.0 configured in Ubuntu.
- A compatible Java JDK for compiling and running the MapReduce jobs.
- Python 3.10 or newer on Windows.
- Git.

The commands below assume the repository is at `C:\hadoop_proj`, the WSL distribution is named `Ubuntu`, and Hadoop is installed at `$HOME/hadoop-3.5.0` inside Ubuntu. Adjust paths and names to match your setup.

## Setup

### 1. Clone the repository

In PowerShell:

```powershell
git clone https://github.com/chethanone/Hadoop-Project.git
cd Hadoop-Project
```

If you already have a checkout, open that project directory instead.

### 2. Create the Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If you prefer not to activate the environment, run its interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Build the MapReduce JAR

From PowerShell, invoke the build script in WSL2:

```powershell
wsl.exe -d Ubuntu -- bash -lc "cd /mnt/c/hadoop_proj && ./compile_mapreduce.sh"
```

Update the `/mnt/c/hadoop_proj` path if your Windows checkout is in a different directory. The build should create or update `jars/mapreduce-jobs.jar`.

### 4. Start Hadoop services

Open Ubuntu in WSL2 and start the Hadoop services required by your configuration, typically the NameNode, DataNode, ResourceManager, and NodeManager. The SecondaryNameNode may also be running depending on your setup.

If Hadoop is installed under `$HOME/hadoop-3.5.0`, its service scripts are under:

```bash
$HOME/hadoop-3.5.0/sbin/
```

Do not format an existing NameNode as a routine troubleshooting step; formatting can destroy access to existing HDFS metadata.

### 5. Run the Flask app

From PowerShell in the project directory:

```powershell
.\.venv\Scripts\python.exe run.py
```

Or, if the virtual environment is activated:

```powershell
python run.py
```

Open **http://127.0.0.1:5000** in your browser.

## Using the Application

| Page | URL | Purpose |
| --- | --- | --- |
| Dashboard | `http://127.0.0.1:5000/dashboard/` | HDFS storage information and recent job statuses |
| MapReduce Lab | `http://127.0.0.1:5000/mapreduce/` | Submit jobs, monitor status, inspect logs, and view results |
| File Manager | Use the application navigation | Browse and manage HDFS files within configured safety boundaries |
| Diagnostics | Use the application navigation | Inspect service connectivity and diagnostic information |

The dashboard and job views depend on Hadoop being available and correctly configured.

## MapReduce Jobs

### WordCount
Counts word occurrences in text input. This demonstrates the typical MapReduce flow: mapping, shuffling, and reducing.

### MatrixMultiplication
Demonstrates matrix multiplication with MapReduce. Use the supplied matrix sample and the input format expected by the Java implementation.

### WeatherAnalysis
Aggregates weather observations by station using the input format expected by the mapper and reducer. The sample input is available at `datasets/weather.csv`.

The compiled job classes are packaged in `jars/mapreduce-jobs.jar`. Rebuild the JAR after modifying Java source code.

## Testing

Run the tests from the repository root after installing the requirements:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests requiring a live Hadoop cluster may be skipped when the cluster is unavailable. The exact test count can change as the test suite evolves; use the current test output as the source of truth.

## Troubleshooting

### Hadoop is not reachable
- Confirm the Ubuntu distribution is running and the required Hadoop daemons are started.
- Review Hadoop configuration and the connection settings used by the application.
- Common default ports are NameNode RPC `9000`, NameNode web UI `9870`, and ResourceManager web UI `8088`. Your configuration may differ.

### A MapReduce job fails
- Verify the input path exists in HDFS and matches the expected input format.
- Inspect job logs and YARN application status.
- Confirm `jars/mapreduce-jobs.jar` contains the expected job classes.
- Rebuild the JAR after changing Java source files.

### Static assets are missing
- Confirm `src/app/static/js/` contains `dashboard.js` and `mapreduce.js`.
- Check the browser developer console and Flask output for missing-file or template errors.
- Ensure templates use Flask's static-file URL handling.

### Python dependencies are missing
- Confirm the virtual environment is active, or use `.venv\Scripts\python.exe` directly.
- Install dependencies with `python -m pip install -r requirements.txt`.

## Safety Notes

- Run the application only in an environment you control.
- Review HDFS paths and operation confirmations before performing file mutations.
- Keep credentials, tokens, local environment files, and machine-specific configuration out of source control.
- Path guardrails are useful safeguards, but they do not replace HDFS permissions or backups.
- Do not commit sample data or logs containing personal, confidential, or otherwise sensitive information.

## Additional Documentation

See the `docs/` directory for the user guide, release notes, performance notes, and project reports.
