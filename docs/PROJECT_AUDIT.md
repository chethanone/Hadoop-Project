# Project Audit: Hadoop File Management and MapReduce Visualization System

**Project Location:** `C:\hadoop_proj` (`/mnt/c/hadoop_proj` in WSL2)  
**Date of Audit:** October 20, 2026  
**Auditor:** Senior Software Architect  
**Document Status:** Final Audit Baseline  

---

## 1. Executive Summary

This audit establishes the baseline technical state for the **Hadoop File Management and MapReduce Visualization System**. The project aims to build a modern, production-grade web application with a responsive dashboard, genuine HDFS file management, live MapReduce execution, and interactive data visualizations.

All claims in this audit are grounded in direct, non-destructive diagnostic inspections of the Windows host and WSL2 Ubuntu environment.

### Key Audit Findings:
1. **Project Directory:** `C:\hadoop_proj` exists and is confirmed **completely empty**.
2. **Hadoop Cluster State:** Apache Hadoop 3.5.0 is **fully operational** inside WSL2 Ubuntu (`/home/chethan/hadoop-3.5.0`). All core daemons (**NameNode**, **DataNode**, **SecondaryNameNode**, **ResourceManager**, **NodeManager**) are currently running with active PIDs.
3. **Cluster Health & Verified Job:** HDFS RPC (`hdfs://localhost:9000`), NameNode JMX/Web UI (port `9870`), and YARN REST API (port `8088`) are active and responsive. An initial real WordCount job (`application_1792483350486_0001`) has executed and verified its output in HDFS (`/user/chethan/wordcount_output/part-r-00000`).
4. **Java Version Discrepancy Identified:** Ubuntu's default system Java is **OpenJDK 21.0.12.1**, whereas Hadoop's environment (`hadoop-env.sh`) is explicitly bound to **OpenJDK 17** (`/usr/lib/jvm/java-17-openjdk-amd64`). All custom MapReduce Java code must be compiled targeting **Java 17 bytecode** to prevent runtime `UnsupportedClassVersionError` exceptions.
5. **Cross-OS Networking Discovery (Critical):** While Windows can directly query NameNode JMX (`:9870`) and YARN REST (`:8088`) via WSL2 localhost mirroring, WebHDFS file read/write operations issue HTTP 307 Temporary Redirects to `http://Astro.localdomain:9864`. Windows host cannot resolve the WSL internal hostname `Astro.localdomain` out-of-the-box. A robust architectural pattern—either redirect hostname re-writing in the client adapter or safe WSL CLI subprocess delegation—is required.
6. **Application Dependencies:** Python is present on both Windows (3.14.8) and WSL2 (3.14.4). Neither runtime has Flask installed yet.

---

## 2. Workspace Audit

| Attribute | Inspected State | Notes |
| :--- | :--- | :--- |
| **Windows Path** | `C:\hadoop_proj` | Confirmed empty directory. |
| **WSL2 Mount Path** | `/mnt/c/hadoop_proj` | Direct DrvFs bind mount; read/write access verified. |
| **Pre-existing Code** | None | No source files, scripts, or virtual environments present. |
| **Source Control** | None (`.git` absent) | Git repository should be initialized in Phase 2. |

---

## 3. Environment Audit

### 3.1 Host OS (Windows)
- **Operating System:** Windows 11 / Windows x86_64
- **Python Runtime:**
  - Located at: `C:\Users\Chethan\AppData\Local\Python\bin\python.exe`
  - Version: **Python 3.14.8**
  - Package Manager: `pip 26.2.1`
  - Note: Windows App Execution Alias points to Microsoft Store shim; the dedicated Python path must be targeted when creating a Windows virtual environment.
  - Installed Packages: Global environment remains unmodified. Local virtual environment (`.venv`) initialized with Python 3.14.8, Flask 3.1.3, Requests 2.34.2, and Pytest 9.1.1.
- **WSL Status:**
  - Version: WSL 2
  - Active Distribution: `Ubuntu` (State: Running, Default: docker-desktop)

### 3.2 Guest OS (WSL2 Ubuntu)
- **Distribution:** Ubuntu (Linux kernel 6.6.x x86_64)
- **Hostname:** `Astro` (`Astro.localdomain`)
- **Python Runtime:**
  - Located at: `/usr/bin/python3`
  - Version: **Python 3.14.4**
  - Package Manager: `pip 25.1.1`
  - Standard library `venv` module: Confirmed functional.
- **Java Runtimes:**
  - System default `/usr/bin/java`: OpenJDK 21.0.12.1 (build 21.0.12.1+1-1-26.04.4-Ubuntu)
  - System default `/usr/bin/javac`: OpenJDK 21.0.12.1
  - Installed JDKs under `/usr/lib/jvm/`:
    - `java-17-openjdk-amd64` (OpenJDK 17.0.x)
    - `java-21-openjdk-amd64` (OpenJDK 21.0.x)
  - Hadoop runtime configuration (`hadoop-env.sh`):
    ```bash
    export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
    ```

---

## 4. Hadoop Cluster Status & Architecture

### 4.1 Hadoop Daemon Verification (`jps`)
The following live processes were verified inside WSL2:

| PID | Daemon | Role | Verified Listening Port / Binding |
| :--- | :--- | :--- | :--- |
| **5953** | `NameNode` | HDFS Master | RPC: `9000`, HTTP Web UI/WebHDFS: `9870` |
| **6085** | `DataNode` | HDFS Block Storage | Data transfer: `9866`, HTTP Web: `9864`, IPC: `9867` |
| **6332** | `SecondaryNameNode` | Checkpoint Node | HTTP Web: `9868` |
| **8766** | `ResourceManager` | YARN Master | Web UI / REST: `8088`, Scheduler: `8030`, ResourceTracker: `8031` |
| **8908** | `NodeManager` | YARN Worker | Container management: `8042` |

### 4.2 Configuration Parameters
- **Installation Directory:** `/home/chethan/hadoop-3.5.0`
- **Hadoop Data Directory:** `/home/chethan/hadoop-data/`
  - NameNode edits/fsimage: `file:///home/chethan/hadoop-data/namenode`
  - DataNode storage: `file:///home/chethan/hadoop-data/datanode`
  - Temporary files: `/home/chethan/hadoop-data/tmp`
- **Core Configuration (`core-site.xml`):**
  - `fs.defaultFS` = `hdfs://localhost:9000`
- **HDFS Configuration (`hdfs-site.xml`):**
  - `dfs.replication` = `1` (Single-node pseudo-distributed cluster)
- **MapReduce Configuration (`mapred-site.xml`):**
  - `mapreduce.framework.name` = `yarn`
  - `yarn.app.mapreduce.am.env` = `HADOOP_MAPRED_HOME=/home/chethan/hadoop-3.5.0`
- **YARN Configuration (`yarn-site.xml`):**
  - `yarn.nodemanager.aux-services` = `mapreduce_shuffle`

### 4.3 Verified HDFS Content & Historical Job Output
A live query of HDFS confirmed active files and prior execution data:
- Root paths: `/tmp`, `/user`
- User path: `/user/chethan`
  - `/user/chethan/sample.txt` (58 bytes, text file containing 3 lines)
  - `/user/chethan/wordcount_output/_SUCCESS` (0 bytes)
  - `/user/chethan/wordcount_output/part-r-00000` (46 bytes)
    - Output content verified:
      ```text
      hadoop	2
      is	3
      mapreduce	1
      powerful	2
      useful	1
      ```
- YARN Application History:
  - Application ID: `application_1792483350486_0001`
  - Name: `word count`
  - State: `FINISHED`, FinalStatus: `SUCCEEDED`

### 4.4 HDFS Storage Metrics (Live JMX Sample)
- Total Capacity: ~1,007 GB (`1,081,101,176,832` bytes)
- Used Capacity: ~976 KB (`999,424` bytes)
- Remaining Capacity: ~951 GB (`1,021,468,577,792` bytes)
- Total Files & Directories: 23
- Total Blocks: 9
- Live DataNodes: 1 (Dead: 0)
- Cluster State: **Operational**

---

## 5. Cross-OS Integration & Networking Analysis

### 5.1 Windows to WSL2 Port Forwarding
WSL2 automatically mirrors localhost ports to Windows for listening TCP sockets.
Direct connection tests from Windows PowerShell confirmed:
- `http://localhost:9870/jmx` -> **HTTP 200 OK** (NameNode metrics)
- `http://localhost:8088/ws/v1/cluster/info` -> **HTTP 200 OK** (YARN metrics)
- `http://localhost:9870/webhdfs/v1/?op=LISTSTATUS` -> **HTTP 200 OK** (Directory listing JSON)

### 5.2 Critical Discovery: WebHDFS 307 Redirect Behavior
When requesting a file read (`op=OPEN`) or file write (`op=CREATE`) via WebHDFS on port 9870:
1. NameNode replies with `HTTP 307 Temporary Redirect`.
2. Header `Location` specifies: `http://Astro.localdomain:9864/webhdfs/v1/...`
3. Because `Astro.localdomain` is an internal Linux hostname, Windows DNS cannot resolve it by default, yielding `curl: (6) Could not resolve host: Astro.localdomain`.
4. When the hostname in the redirect URL is manually rewritten to `localhost:9864`, the request succeeds instantly and delivers the file content.

### 5.3 Communication Architecture Options

| Strategy | Architecture | Pros | Cons | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Strategy A: Pure Subprocess Bridge** | Flask on Windows executes `wsl.exe -d Ubuntu -- /home/chethan/hadoop-3.5.0/bin/hdfs ...` | 100% reliable; bypasses WebHDFS redirect issues; immune to hostname resolution; direct CLI fidelity. | Subprocess overhead (~60ms per invocation); requires path translation. | **Primary for file mutations & MapReduce execution.** |
| **Strategy B: Hybrid REST + Redirect Rewriter** | Windows Flask uses HTTP REST for JMX/YARN, and rewrites `Astro.localdomain` -> `127.0.0.1` for WebHDFS streaming. | Fast JSON reads; non-blocking file streaming; no subprocess latency for metrics. | Requires custom `requests.Session` redirect hook. | **Primary for dashboard metrics, cluster telemetry, and text preview streaming.** |
| **Strategy C: Native WSL Flask App** | Flask runs inside WSL2; Windows browser accesses `http://localhost:5000`. | Zero cross-OS latency; native Linux environment; direct Java & Hadoop access. | Minor divergence from "Windows-hosted Flask" phrasing, though fully accessible from Windows browser. | **Supported as an alternative run-target via identical codebase.** |

**Architectural Decision:** Implement a **Modular Hadoop Bridge Adapter** in Python. The adapter will use **REST/JMX APIs** with redirect hostname normalization for high-frequency dashboard queries and file streaming, and **safe `wsl.exe` subprocess argument lists** for MapReduce job execution and filesystem mutations.

---

## 6. Fact Verification Matrix

| Area | Verified Fact | Technical Assumption | Unverified Prerequisite / Action Required |
| :--- | :--- | :--- | :--- |
| **Project Workspace** | `C:\hadoop_proj` is empty. | Project will be developed in this directory. | Initialize directory structure and Git. |
| **HDFS Master** | NameNode is active on port 9000 & 9870. | Stays healthy during app lifetime. | Verify NameNode restart recovery script. |
| **HDFS Data** | DataNode active on port 9864/9866. | Single replica is sufficient. | Configure custom redirect handling in client. |
| **YARN** | RM (8088) & NM (8042) running. | Adequate container memory for 3 jobs. | Validate container allocation under load. |
| **Java for Hadoop** | Hadoop uses OpenJDK 17. | OpenJDK 17 javac must be used for compilation. | Ensure build scripts explicitly invoke OpenJDK 17. |
| **Java for System** | System default is OpenJDK 21. | Mixing versions causes bytecode errors. | Explicitly configure compilation flags (`--release 17`). |
| **Python Host** | Python 3.14.8 on Windows. | Compatible with Flask & dependencies. | Must create virtual environment and install Flask. |
| **Python WSL** | Python 3.14.4 on Ubuntu. | Can run backend or helper scripts. | Virtual environment ready if WSL runtime used. |
| **MapReduce: WordCount** | Standard algorithm verified in HDFS. | Custom Java class can be compiled cleanly. | Implement clean standalone Java source & packaging. |
| **MapReduce: Matrix Mult** | Not yet implemented in cluster. | Two-step or single-step algorithm needed. | Design matrix input format, mapper, and reducer. |
| **MapReduce: Weather** | Not yet implemented in cluster. | Needs clean CSV schema and parser. | Acquire/generate structured NOAA-style weather dataset. |

---

## 7. Security & Safety Baseline

1. **Subprocess Injection Defense:**
   - Prohibit all `shell=True` invocations.
   - All WSL commands must be passed as explicit token arrays (e.g., `["wsl.exe", "-d", "Ubuntu", "--", "/home/chethan/hadoop-3.5.0/bin/hdfs", "dfs", "-ls", target_path]`).
2. **Path Traversal Defense:**
   - User-supplied HDFS paths must be normalized and strictly validated.
   - Forbid directory traversal tokens (`..`), path escaping, and control characters.
   - Restrict user modifications to designated HDFS namespaces (e.g., `/user/chethan/` or configurable root).
3. **Destructive Operation Protection:**
   - Permanent deletions (`-rm -r`) must require an explicit frontend confirmation token and CSRF validation.
   - Core Hadoop system paths (`/`, `/tmp`, `/home/chethan/hadoop-data`) are read-only or strictly protected against modification.
4. **Hadoop Cluster Integrity:**
   - `hdfs namenode -format` is strictly forbidden across all application code, scripts, and documentation.
   - Existing cluster configuration files (`core-site.xml`, `hdfs-site.xml`, `yarn-site.xml`) are read-only to the web application.

---

## 8. Audit Conclusion

The underlying Hadoop 3.5.0 environment in WSL2 is healthy, verified, and ready for integration. The primary architectural challenges—cross-OS boundary communication, WebHDFS DataNode hostname resolution, and Java 17 bytecode alignment—have been diagnosed with concrete solutions.

Proceeding to Phase 2 will require user approval of this audit and the accompanying Implementation Plan (`docs/IMPLEMENTATION_PLAN.md`).
