# Phase 2 Completion Report: Environment Initialization & Core Hadoop Bridge

**Project:** Hadoop File Management and MapReduce Visualization System  
**Document:** `docs/PHASE2_REPORT.md`  
**Execution Date:** October 20, 2026  
**Status:** Completed & Fully Verified  

---

## 1. Executive Summary

Phase 2 has successfully established the application foundation, secure cross-OS communication bridge, and real-time cluster diagnostics. The Flask web application runs on Windows in an isolated project virtual environment (`.venv`) and safely interacts with the active Apache Hadoop 3.5.0 cluster inside WSL2 Ubuntu without altering cluster configurations, stopping daemons, or modifying existing HDFS data.

All 27 automated unit and live integration tests passed with 100% success.

---

## 2. Deliverables & Files Created

| Path | Purpose / Description |
| :--- | :--- |
| `.gitignore` | Ignores `.venv`, caches, bytecode, environment secrets, and build outputs. |
| `requirements.txt` | Pinned dependency specifications for production and test tooling. |
| `run.py` | Standalone application entry point. |
| `src/app/__init__.py` | Flask application factory (`create_app`), template filter registration. |
| `src/app/config.py` | Strongly-typed configuration with environment variable support. |
| `src/app/routes/__init__.py` | Route blueprint packaging. |
| `src/app/routes/diagnostics.py` | Diagnostics page route and read-only JSON API endpoints. |
| `src/app/services/__init__.py` | Services layer package exports. |
| `src/app/services/hadoop_adapter.py` | Hardened bridge: `wsl.exe` safe argument runner, WebHDFS redirect normalizer, path sanitizer, and JMX/REST client. |
| `src/app/static/css/custom.css` | Premium dark-mode design system with glassmorphism, responsive cards, and live status pulses. |
| `src/app/templates/base.html` | Base HTML layout with Bootstrap 5, Bootstrap Icons, Plus Jakarta Sans, and navigation bar. |
| `src/app/templates/diagnostics.html` | Comprehensive diagnostics UI with live subsystem status cards, JVM daemon table, and interactive HDFS file preview modal. |
| `tests/__init__.py` | Test suite initialization. |
| `tests/test_config.py` | Unit tests for configuration defaults and environment overrides. |
| `tests/test_path_validation.py` | Unit tests for path traversal, control character, and shell injection prevention. |
| `tests/test_redirect_validation.py` | Unit tests for WebHDFS redirect host validation, SSRF defense, and normalization. |
| `tests/test_hadoop_adapter_unit.py` | Unit tests using mocks for timeout handling, CLI fallback, and error handling. |
| `tests/test_live_integration.py` | Live integration tests against active WSL2 Hadoop cluster and real HDFS data. |
| `docs/PROJECT_AUDIT.md` | Updated with verified local environment details. |
| `docs/PHASE2_REPORT.md` | This report. |

---

## 3. Verified Dependency Manifest

The local project virtual environment was initialized at `C:\hadoop_proj\.venv` using Windows Python 3.14.8:

- `Flask == 3.1.3`
- `requests == 2.34.2`
- `python-dotenv == 1.2.4`
- `Werkzeug == 3.1.9`
- `Jinja2 == 3.1.6`
- `MarkupSafe == 3.0.4`
- `itsdangerous == 2.2.0`
- `click == 8.5.0`
- `blinker == 1.9.0`
- `urllib3 == 2.8.0`
- `certifi == 2026.10.19`
- `charset-normalizer == 3.5.2`
- `idna == 3.20`
- `pytest == 9.1.1`

Global system Python packages were untouched.

---

## 4. Test Execution & Live Verification Results

The automated test suite was executed via `.venv\Scripts\pytest.exe -v`:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.8, pytest-9.1.1, pluggy-1.7.0 -- C:\hadoop_proj\.venv\Scripts\python.exe
rootdir: C:\hadoop_proj
collected 27 items

tests/test_config.py::test_base_config_defaults PASSED                   [  3%]
tests/test_config.py::test_config_environments PASSED                    [  7%]
tests/test_hadoop_adapter_unit.py::test_subprocess_timeout_handling PASSED [ 11%]
tests/test_hadoop_adapter_unit.py::test_check_wsl_status_offline PASSED  [ 14%]
tests/test_hadoop_adapter_unit.py::test_get_namenode_jmx_connection_refused PASSED [ 18%]
tests/test_hadoop_adapter_unit.py::test_get_yarn_cluster_info_500_error PASSED [ 22%]
tests/test_hadoop_adapter_unit.py::test_list_hdfs_directory_fallback_to_cli PASSED [ 25%]
tests/test_live_integration.py::test_live_wsl_status PASSED              [ 29%]
tests/test_live_integration.py::test_live_hadoop_cli PASSED              [ 33%]
tests/test_live_integration.py::test_live_jps_processes PASSED           [ 37%]
tests/test_live_integration.py::test_live_namenode_jmx PASSED            [ 40%]
tests/test_live_integration.py::test_live_yarn_cluster_info PASSED       [ 44%]
tests/test_live_integration.py::test_live_hdfs_user_directory_listing PASSED [ 48%]
tests/test_live_integration.py::test_live_sample_text_preview_and_fidelity PASSED [ 51%]
tests/test_live_integration.py::test_live_wordcount_output_unaltered PASSED [ 55%]
tests/test_live_integration.py::test_flask_diagnostics_page_loads PASSED [ 59%]
tests/test_live_integration.py::test_flask_api_diagnostics_endpoint PASSED [ 62%]
tests/test_live_integration.py::test_flask_api_path_traversal_blocked PASSED [ 66%]
tests/test_path_validation.py::test_valid_paths PASSED                   [ 70%]
tests/test_path_validation.py::test_reject_relative_or_empty_paths PASSED [ 74%]
tests/test_path_validation.py::test_reject_path_traversal PASSED         [ 77%]
tests/test_path_validation.py::test_reject_dangerous_characters PASSED   [ 81%]
tests/test_redirect_validation.py::test_normalize_verified_wsl_host PASSED [ 85%]
tests/test_redirect_validation.py::test_preserve_trusted_loopback_hosts PASSED [ 88%]
tests/test_redirect_validation.py::test_reject_untrusted_redirect_hosts PASSED [ 92%]
tests/test_redirect_validation.py::test_reject_invalid_schemes PASSED    [ 96%]
tests/test_redirect_validation.py::test_reject_empty_redirect_url PASSED [100%]

============================= 27 passed in 23.00s =============================
```

### Key Verification Checkpoints Confirmed:
1. **WSL2 Subsystem:** Confirmed online (`Linux 6.18.54.1-microsoft-standard-WSL2 x86_64`).
2. **Hadoop CLI:** Version 3.5.0 verified via `wsl.exe` subprocess array.
3. **Active JVM Daemons:** Verified live PIDs for NameNode (`5953`), DataNode (`6085`), SecondaryNameNode (`6332`), ResourceManager (`8766`), and NodeManager (`8908`).
4. **NameNode JMX Telemetry:** Live cluster capacity: ~1,007 GB total (`1,081,101,176,832` bytes), 23 total files, 9 total blocks, 1 live DataNode, `FSState: Operational`.
5. **YARN REST API:** Verified cluster state `STARTED`, HA state `ACTIVE`, 1 completed application.
6. **Data Fidelity & Existing HDFS Files:**
   - `/user/chethan/sample.txt` previewed via WebHDFS redirect rewriter (58 bytes, 3 lines); content intact.
   - `/user/chethan/wordcount_output/part-r-00000` previewed (46 bytes, 5 word pairs); content 100% unaltered.
7. **Security Guardrail Tests:**
   - Path traversal vectors (`../../etc/passwd`, `/user/../etc`) strictly blocked with HTTP 400 `HadoopPathError`.
   - Shell metacharacters (`;`, `|`, `&`, `$`, null bytes) strictly blocked with HTTP 400.
   - Untrusted WebHDFS redirect hosts (`evil.com`, unauthorized IPs) blocked with `HadoopRedirectError`.

---

## 5. How to Launch the Application

To run the application manually from Windows PowerShell or Command Prompt:

```powershell
# Navigate to project root
cd C:\hadoop_proj

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Start the Flask web application
python run.py
```

The application will start on: **`http://127.0.0.1:5000`** (or `http://localhost:5000`).  
Navigating to `http://localhost:5000/diagnostics` presents the live system diagnostics dashboard.

---

## 6. Unresolved Issues

None. All Phase 2 objectives, safety constraints, cross-OS integration patterns, and tests are complete and verified.

---

## 7. Next Steps (Pending Approval)

Phase 2 is complete. In accordance with the project instructions, work is stopped here pending user review and approval to proceed to **Phase 3 — Real HDFS File Manager** (directory browsing, safe upload, safe download, mkdir, copy, rename, and confirmation-guarded deletion).
