# Implementation Plan: Hadoop File Management and MapReduce Visualization System

**Project:** Hadoop File Management & MapReduce Visualization System  
**Document:** `docs/IMPLEMENTATION_PLAN.md`  
**Version:** 1.0.0  
**Target Platform:** Windows Host + WSL2 Ubuntu Guest (Apache Hadoop 3.5.0)  

---

## 1. Architectural Blueprint & Cross-OS Strategy

### 1.1 Architecture Overview
The system bridges a modern Python Flask web application on Windows with a single-node Apache Hadoop 3.5.0 installation running inside WSL2 Ubuntu.

```mermaid
flowchart TB
    subgraph Browser ["Web Browser (User Interface)"]
        UI["Bootstrap 5 + Chart.js Dashboard\n• HDFS Explorer\n• MapReduce Laboratory\n• Real-Time Visualizations\n• Cluster Diagnostics"]
    end

    subgraph Host ["Host: Windows (C:\\hadoop_proj)"]
        Flask["Flask Web Application\n(Python 3.14 venv)\n• REST API & HTML Views\n• Path Sanitizer & Guard\n• Job Runner & Output Parser"]
        Adapter["Hadoop Bridge Adapter\n• Safe Subprocess Argument Generator\n• WebHDFS Redirect Host Rewriter\n• YARN REST Client"]
    end

    subgraph Guest ["WSL2 Ubuntu (Astro /mnt/c/hadoop_proj)"]
        HadoopCLI["Hadoop CLI & Java Compiler\n• /home/chethan/hadoop-3.5.0/bin/hdfs\n• /home/chethan/hadoop-3.5.0/bin/hadoop\n• /usr/lib/jvm/java-17-openjdk-amd64/bin/javac"]
        
        subgraph Cluster ["Hadoop 3.5.0 Daemons"]
            NN["NameNode (:9000 RPC, :9870 Web/JMX)"]
            DN["DataNode (:9864 Web, :9866 Data)"]
            RM["ResourceManager (:8088 REST/Web)"]
            NM["NodeManager (:8042)"]
        end
    end

    UI <-->|HTTP / JSON / HTML| Flask
    Flask --> Adapter
    Adapter -->|HTTP JMX / WebHDFS / YARN REST| NN
    Adapter -->|HTTP WebHDFS Stream (Host Rewritten)| DN
    Adapter -->|HTTP Cluster REST API| RM
    Adapter -->|wsl.exe -d Ubuntu [Safe Array]| HadoopCLI
    HadoopCLI -->|Job Submission & HDFS IPC| Cluster
```

### 1.2 Cross-OS Integration Mechanics

1. **JMX & Telemetry Gathering:**
   - The Flask backend connects to `http://localhost:9870/jmx` and `http://localhost:8088/ws/v1/cluster/` directly via Windows localhost port forwarding.
   - Non-blocking HTTP calls deliver real-time cluster metrics (total capacity, used blocks, active datanodes, running applications).

2. **HDFS File Operations:**
   - **Directory Listing & Metadata:** Sourced via WebHDFS `LISTSTATUS` or `hdfs dfs -ls` depending on network availability.
   - **File Content & Text Preview:** WebHDFS `OPEN` issues an HTTP 307 redirect pointing to `Astro.localdomain:9864`. The Python `HadoopClient` intercepts the redirect, replaces `Astro.localdomain` with `127.0.0.1`, and streams the data chunk directly to the browser.
   - **Uploads & Mutations:** Handled through parameterized `wsl.exe -d Ubuntu -- /home/chethan/hadoop-3.5.0/bin/hdfs dfs ...` executions with strict argument tokenization.

3. **MapReduce Execution Engine:**
   - Java MapReduce sources compiled using OpenJDK 17 with Hadoop classpath inside WSL.
   - Submissions executed via `wsl.exe -d Ubuntu -- hadoop jar <jar-path> <job-class> <input-path> <output-path>`.
   - Execution is tracked asynchronously:
     - Background worker captures stdout/stderr.
     - YARN REST API polls live Map and Reduce percentages.
     - Terminal output and exit code confirm true completion.
   - Result parser reads `part-r-00000` from HDFS and transforms raw tab-delimited records into structured JSON for Chart.js.

---

## 2. Target Directory Structure

The project will be organized cleanly in `C:\hadoop_proj`:

```text
C:\hadoop_proj\
├── docs\
│   ├── PROJECT_AUDIT.md            # Environment & prerequisites audit
│   └── IMPLEMENTATION_PLAN.md      # This comprehensive plan
├── src\
│   ├── app\
│   │   ├── __init__.py             # Flask application factory
│   │   ├── config.py               # App configuration & constants
│   │   ├── routes\
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py        # Dashboard & cluster stats routes
│   │   │   ├── file_manager.py     # HDFS file operations routes
│   │   │   ├── mapreduce.py        # Job submission & monitoring routes
│   │   │   ├── datasets.py         # Dataset management routes
│   │   │   └── diagnostics.py      # Health & environment routes
│   │   ├── services\
│   │   │   ├── __init__.py
│   │   │   ├── hadoop_adapter.py   # WSL subprocess & WebHDFS bridge
│   │   │   ├── hdfs_service.py     # HDFS business logic & safety checks
│   │   │   ├── yarn_service.py     # YARN job monitoring & REST client
│   │   │   ├── job_runner.py       # Async background job executor
│   │   │   └── visualizer.py       # Data parsers for Chart.js
│   │   ├── static\
│   │   │   ├── css\
│   │   │   │   └── custom.css      # Premium dark/light themes & styling
│   │   │   └── js\
│   │   │       ├── dashboard.js    # Cluster status charts
│   │   │       ├── file_manager.js # HDFS explorer & modal interactions
│   │   │       ├── mapreduce.js    # Job launcher & live log console
│   │   │       └── visualizations.js # WordCount, Matrix, Weather charts
│   │   └── templates\
│   │       ├── base.html           # Core layout, navbar & sidebar
│   │       ├── dashboard.html      # Overview & cluster gauges
│   │       ├── file_manager.html   # HDFS browser & file viewer
│   │       ├── mapreduce.html      # MapReduce laboratory & log stream
│   │       ├── datasets.html       # Sample data manager
│   │       ├── diagnostics.html    # Process status & connectivity tests
│   │       └── about.html          # Project architecture & user guide
│   └── mapreduce\
│       ├── build.py                # Compilation helper script (Java 17)
│       ├── pom.xml                 # Optional Maven descriptor
│       └── java\
│           └── com\
│               └── hadoop\
│                   ├── wordcount\
│                   │   └── WordCount.java
│                   ├── matrix\
│                   │   └── MatrixMultiplication.java
│                   └── weather\
│                       └── WeatherAnalysis.java
├── datasets\
│   ├── wordcount\
│   │   ├── sample_text_small.txt
│   │   └── sample_literature.txt
│   ├── matrix\
│   │   ├── matrix_A_small.txt
│   │   └── matrix_B_small.txt
│   └── weather\
│       ├── weather_data_sample.csv
│       └── weather_stations.csv
├── tests\
│   ├── test_security_paths.py      # Path traversal & injection tests
│   ├── test_hdfs_adapter.py        # HDFS service integration tests
│   ├── test_yarn_service.py        # YARN API mock/real tests
│   └── test_acceptance_real.py     # Live HDFS & MapReduce proof tests
├── scripts\
│   ├── setup_env.bat               # Windows venv setup script
│   ├── run_app.bat                 # Windows application launcher
│   └── compile_jobs.bat            # Cross-OS compilation trigger
├── requirements.txt                # Python package specifications
└── run.py                          # Application entry point
```

---

## 3. Staged Implementation Phases

### Phase 2: Environment Initialization & Core Hadoop Bridge
**Objectives:**
- Create Python virtual environment and configure `requirements.txt` (`Flask`, `requests`, `python-dotenv`).
- Build the Flask application factory (`src/app/__init__.py`) with modular blueprint architecture.
- Build `HadoopAdapter` (`src/app/services/hadoop_adapter.py`):
  - Safe subprocess invocation wrapping `wsl.exe -d Ubuntu -- <command>` with strict token lists.
  - Windows <-> WSL path translator (`C:\hadoop_proj` <-> `/mnt/c/hadoop_proj`).
  - WebHDFS redirect hostname normalizer (rewriting `Astro.localdomain` to `127.0.0.1`).
- Implement the Environment Diagnostics endpoint (`/diagnostics`):
  - Query NameNode JMX, DataNode status, ResourceManager state, and local WSL processes (`jps`).
  - Output transparent diagnostic health checks without masking errors.

### Phase 3: Real HDFS File Manager
**Objectives:**
- Implement HDFS directory traversal (`/file-manager`):
  - Display directory tree, filenames, permissions, replication, owner, group, size, and modification date.
  - Sourced directly from HDFS via `LISTSTATUS`.
- Implement directory creation (`mkdir`):
  - Validate parent directory and sanitized directory name.
- Implement file uploads:
  - Stream uploaded files from Windows into HDFS via safe temp staging or WebHDFS.
- Implement file preview and download:
  - Read first 500 lines or 1 MB of text files safely; return binary streams for downloads.
- Implement file operations:
  - Copy (`-cp`), Rename/Move (`-mv`), Delete (`-rm -r`).
- Implement strict security safeguards:
  - Confirmation modal for destructive operations.
  - Protection against deleting root `/`, `/user`, `/tmp`, or `/home/chethan`.

### Phase 4: Java MapReduce Programs & Compilation Engine
**Objectives:**
- Implement 3 genuine, self-contained Java MapReduce applications:
  1. **Word Count (`WordCount.java`):**
     - Mapper: Tokenizes text, strips punctuation, normalizes case, emits `(word, 1)`.
     - Reducer: Sums counts, emits sorted `(word, total)`.
     - Combiner optimization enabled.
  2. **Matrix Multiplication (`MatrixMultiplication.java`):**
     - Computes the matrix product $C = A \times B$.
     - Input format: `MatrixName,RowIndex,ColIndex,Value`.
     - Mapper: Replicates elements to necessary row/column coordinate keys.
     - Reducer: Performs dot product summation for cell $(i, j)$ and emits `Row,Col,Value`.
  3. **Weather CSV Processing (`WeatherAnalysis.java`):**
     - Parses structured NOAA-format weather records (Year, Month, StationID, MaxTemp, MinTemp, Precipitation).
     - Mapper: Extracts Year/Station and Temperature, filtering invalid/missing values (e.g., `9999`).
     - Reducer: Computes Maximum, Minimum, and Average temperatures per Year or Station.
- Build compilation pipeline (`src/mapreduce/build.py`):
  - Invokes OpenJDK 17 `javac` inside WSL targeting Java 17 bytecode:
    `javac -cp "$(/home/chethan/hadoop-3.5.0/bin/hadoop classpath)" -d build/ ...`
  - Packages compiled classes into `dist/hadoop-mapreduce-jobs.jar`.
- Provide verified sample datasets for each job in `datasets/`.

### Phase 5: MapReduce Execution Laboratory & Job Tracking
**Objectives:**
- Build Job Submission Interface (`/mapreduce`):
  - Job selection dropdown (WordCount, Matrix Multiplication, Weather Analysis).
  - Input path selector (browse existing HDFS files or upload sample datasets).
  - Configurable output directory with automatic non-destructive timestamp suffixing.
  - Execution parameters (number of reducers, custom delimiters).
- Implement Asynchronous Execution Runner (`src/app/services/job_runner.py`):
  - Spawns background thread for job execution.
  - Streams live stderr/stdout into a ring buffer for real-time frontend polling.
  - Polls YARN ResourceManager REST API (`/ws/v1/cluster/apps/{appId}`) for live state, progress percentage, and memory usage.
- Implement Result Extraction:
  - Read `_SUCCESS` and `part-r-00000` from HDFS.
  - Distinguish genuine job completion from partial failures or runtime crashes.
  - Prevent fake/mocked results: if the job fails, show real YARN container logs and stack traces.

### Phase 6: Frontend Dashboard, Visualizations & UX Polish
**Objectives:**
- Design a high-aesthetic, responsive dashboard using Bootstrap 5, custom CSS (glassmorphism/subtle elevation), and Chart.js.
- Dashboard Visualizations:
  - HDFS Storage Gauge: Doughnut chart showing Used, Available, and Total HDFS Capacity from JMX.
  - Cluster Object Distribution: Bar chart of files, blocks, and replication status.
  - YARN Job History: Timeline/bar chart of recent jobs, duration, and status.
- MapReduce Result Visualizers:
  - **WordCount Visualizer:** Top 20 word frequency horizontal bar chart + search filter.
  - **Matrix Visualizer:** Interactive 2D matrix grid / heatmap displaying product matrix cells.
  - **Weather Visualizer:** Dual-axis line and bar chart showing Annual Max/Min Temperatures and precipitation patterns.
- UX Polish:
  - Status badges, toast notifications for copy/delete actions, responsive breadcrumbs, and live log terminal with auto-scroll.

### Phase 7: Acceptance Testing, Hardening & Documentation
**Objectives:**
- Execute End-to-End Acceptance Test suite against real HDFS and YARN.
- Conduct security hardening tests (path traversal fuzzing, invalid parameters).
- Finalize user and technical documentation (`docs/USER_GUIDE.md`, `README.md`).

---

## 4. Acceptance Test Plan (Real HDFS & Real MapReduce)

The application must prove its integration with real Hadoop services. Mock data is strictly forbidden in acceptance testing.

| Test ID | Test Name | Action / Trigger | Verification Method | Pass Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **AT-01** | **Live HDFS Telemetry** | Load Dashboard (`/`) | Query `http://localhost:9870/jmx` | Total capacity matches ~1,007 GB; DataNode count = 1; FilesTotal >= 23. |
| **AT-02** | **HDFS File Listing** | Navigate to `/user/chethan` | Inspect rendered file table | Table displays `sample.txt` (58 B) and `wordcount_output/` from existing HDFS. |
| **AT-03** | **Safe Text Preview** | Click Preview on `sample.txt` | Read stream from WebHDFS | Preview displays exact 3 lines (`hadoop is powerful...`). |
| **AT-04** | **HDFS File Creation** | Upload test file `test_audit.txt` | Execute `hdfs dfs -put` via adapter | File appears in HDFS listing; verification via `hdfs dfs -ls` in WSL. |
| **AT-05** | **Safe Deletion** | Delete `test_audit.txt` with modal confirmation | Execute `hdfs dfs -rm` via adapter | File disappears from HDFS; destructive action logged; protected dirs reject deletion. |
| **AT-06** | **Java 17 Compilation** | Run `compile_jobs.bat` | Check bytecode version via `javap -v` | All `.class` files compiled with `major version: 61` (Java 17). |
| **AT-07** | **Real WordCount Run** | Submit WordCount job on `datasets/wordcount/` | Monitor YARN REST API | YARN assigns valid `application_...` ID; exit code 0; `_SUCCESS` created in HDFS. |
| **AT-08** | **WordCount Chart** | View WordCount results | Inspect Chart.js rendering | Chart dynamically plots exact frequencies parsed from `part-r-00000`. |
| **AT-09** | **Real Matrix Mult Run** | Submit Matrix Multiplication job on $3 \times 3$ matrices | Monitor YARN execution | Result cells in `part-r-00000` match mathematical matrix product $C = A \times B$. |
| **AT-10** | **Real Weather Analysis** | Submit Weather job on sample weather CSV | Monitor YARN execution | Yearly Max/Min temperatures correctly aggregated in HDFS output and plotted. |
| **AT-11** | **Security Path Traversal** | Submit path `../../etc/passwd` to File Manager | Validate path guard response | Request blocked with HTTP 400/403; zero filesystem escape. |
| **AT-12** | **Cluster Fault Handling** | Temporarily simulate stopped daemon | Check `/diagnostics` | UI clearly flags specific daemon as "Offline" rather than throwing generic 500 error. |

---

## 5. Security Controls & Safety Safeguards

### 5.1 Subprocess Injection Prevention
- **Rule:** Never invoke `shell=True` in Python `subprocess`.
- **Implementation:** Commands are passed as structured lists:
  ```python
  # Safe Subprocess Pattern
  args = ["wsl.exe", "-d", "Ubuntu", "--", HADOOP_BIN, "dfs", "-ls", sanitized_path]
  result = subprocess.run(args, capture_output=True, text=True, timeout=30)
  ```

### 5.2 Path Traversal & Scope Restrictions
- **Rule:** All HDFS path inputs must be canonicalized and checked against allowed prefixes.
- **Implementation:**
  - Reject paths containing `..`, null bytes (`\0`), or shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`).
  - Restrict write and delete operations strictly to `/user/chethan/` or configurable workspace directory `/app_data/`.
  - Disallow destructive operations on root `/`, `/user`, `/tmp`, and Hadoop system paths.

### 5.3 Hadoop Configuration & Data Immutability
- **Safety Invariant:** Under no circumstances will `hdfs namenode -format` be invoked or included in any script.
- Cluster configuration files under `/home/chethan/hadoop-3.5.0/etc/hadoop/` are strictly read-only.

### 5.4 Graceful Error Handling & Diagnostics
- If a Hadoop daemon is unreachable, the system must clearly report:
  - Target component (e.g., NameNode on port 9870 or YARN on port 8088).
  - Detected state (Connection Refused, Timeout, Host Unreachable).
  - Suggested remediation command (e.g., `start-dfs.sh` or `start-yarn.sh` in WSL).

---

## 6. Risk Register & Mitigation Strategies

| Risk | Impact | Probability | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **WSL2 DataNode Hostname Resolution** | High | High (Verified) | WebHDFS redirect hostname rewriter in Python adapter rewrites `Astro.localdomain` to `127.0.0.1`. Subprocess HDFS CLI serves as fallback. |
| **Java Bytecode Version Mismatch** | High | Medium (Identified) | Build script explicitly invokes OpenJDK 17 compiler (`/usr/lib/jvm/java-17-openjdk-amd64/bin/javac`) with `--release 17` flag. |
| **Long-Running Job Timeouts** | Medium | Medium | MapReduce execution executed in background worker threads; progress tracked via polling YARN REST API instead of blocking HTTP requests. |
| **Accidental HDFS Data Deletion** | Critical | Low | Frontend requires explicit confirmation typing/modal; backend enforces path whitelist protecting core directories. |
| **YARN Memory Starvation** | Medium | Low | Sample datasets sized appropriately (10 KB – 5 MB) for single-node cluster resource boundaries. |

---

## 7. Approval & Sign-Off Gate

This Implementation Plan concludes Phase 1. Execution of **Phase 2 (Environment Initialization & Core Hadoop Bridge)** will begin immediately upon user review and approval.
