# Phase 3 Completion Report: Real HDFS File Manager

**Project:** Hadoop File Management and MapReduce Visualization System  
**Document:** `docs/PHASE3_REPORT.md`  
**Execution Date:** October 20, 2026  
**Status:** Completed & Fully Verified  

---

## 1. Executive Summary

Phase 3 has successfully implemented full, genuine HDFS file-management functionality. The system enables users to browse HDFS directories hierarchically with interactive breadcrumbs, upload local files via zero-copy host staging, download files as binary streams, create directories, copy items, rename items, and perform deletions with explicit safety confirmation for directories.

All operations execute directly against the real Apache Hadoop 3.5.0 cluster in WSL2 Ubuntu (`hdfs://localhost:9000`). No mock data or simulated responses were used. Strict protection mechanisms prevent accidental modification or deletion of core cluster assets (`/user/chethan/sample.txt` and `/user/chethan/wordcount_output/`), and all mutation testing was executed within an isolated, ephemeral sandbox directory (`/user/chethan/phase3_test_sandbox/`).

The entire test suite—now totaling **42 automated unit and live integration tests**—passed with 100% success.

---

## 2. Deliverables & Modified Files

| Path | Status | Purpose / Description |
| :--- | :--- | :--- |
| `src/app/config.py` | Modified | Added `PROTECTED_HDFS_PATHS`, `TEMP_STAGING_DIR`, and `MAX_UPLOAD_SIZE_BYTES`. |
| `.gitignore` | Modified | Added `.temp_staging/` to prevent tracking local upload staging artifacts. |
| `src/app/services/hadoop_adapter.py` | Modified | Added new exceptions (`ProtectedPathError`, `HadoopItemExistsError`, `HadoopNotFoundError`), `win_to_wsl_path`, `check_protected_path`, `exists`, `is_directory`, `mkdir`, `put_file`, `copy_item`, `rename_item`, `delete_item`, and `stream_file_content`. |
| `src/app/services/hdfs_service.py` | Created | High-level coordinator for breadcrumb generation, item name sanitization, upload staging/cleanup, and protected path tagging. |
| `src/app/services/__init__.py` | Modified | Exported `HdfsService` and Phase 3 exception classes. |
| `src/app/routes/file_manager.py` | Created | File manager blueprint handling `/file-manager`, `/api/files/browse`, `/api/files/download`, `/api/files/mkdir`, `/api/files/upload`, `/api/files/copy`, `/api/files/rename`, and `/api/files/delete`. |
| `src/app/routes/__init__.py` | Modified | Exported `file_manager_bp`. |
| `src/app/__init__.py` | Modified | Registered `file_manager_bp` in application factory. |
| `src/app/templates/base.html` | Modified | Activated "File Manager" link in navigation bar. |
| `src/app/templates/file_manager.html` | Created | Modern dark-mode file explorer with breadcrumbs, action toolbar, responsive data table, and modals for folder creation, upload, copy, rename, deletion confirmation, and file preview. |
| `tests/test_hdfs_service_unit.py` | Created | Unit tests for item sanitization, breadcrumb generation, parent path resolution, protected annotation, and upload staging cleanup. |
| `tests/test_hdfs_mutations_live.py` | Created | Live integration tests executing within an isolated sandbox (`/user/chethan/phase3_test_sandbox/`) verifying real mkdir, upload, preview, copy, rename, delete, recursive confirmation, and protection guardrails. |
| `docs/PHASE3_REPORT.md` | Created | This report. |

---

## 3. Implemented Capabilities & Safety Architecture

### 3.1 Hierarchical Directory Browsing & Navigation
- **Dynamic Breadcrumbs:** Clicking any segment (e.g. `Root (/)` &rarr; `user` &rarr; `chethan`) immediately navigates to that path.
- **Detailed Metadata:** Displays item name, type badge (`DIRECTORY` / `FILE`), formatted file size (`format_bytes`), POSIX octal permissions, owner/group (`chethan:supergroup`), and last modification timestamp.
- **Protected Space Badging:** Items matching protected system paths are tagged with a "Protected" badge and destructive buttons are disabled in the UI.

### 3.2 Secure Zero-Copy File Uploads
- Client upload streams are initially saved to a temporary local staging directory (`C:\hadoop_proj\.temp_staging\`) on the Windows host.
- The path is translated to WSL DrvFs format (`/mnt/c/hadoop_proj/.temp_staging/<uuid>_<filename>`), allowing Hadoop CLI in WSL to ingest the file directly via `hdfs dfs -put` without network socket overhead.
- In all scenarios (success or failure), the temporary staging file is deleted immediately in a `finally` block.
- Maximum upload size is enforced (100 MB default ceiling).

### 3.3 Streaming File Downloads
- File downloads stream content in chunks directly from WebHDFS (using normalized redirect host rewriting to bypass `Astro.localdomain` resolution issues) with seamless fallback to streaming `hdfs dfs -cat`.
- Sets proper `Content-Disposition: attachment; filename="<name>"` headers.

### 3.4 Unmistakable Deletion Confirmation Gate
- **Single Files:** Can be deleted with standard confirmation modal.
- **Directories:** Because directory deletion in HDFS is recursive (`hdfs dfs -rm -r`), accidental data loss is prevented by an interactive safety gate:
  - The UI explicitly informs the user that directory deletion is recursive.
  - The user must type the **exact directory name** into a verification input field before the "Permanently Delete" button becomes active.
  - The backend verifies that the received `confirmation_name` matches the directory basename before executing the deletion command.

### 3.5 Core System Asset Protection (`ProtectedPathError`)
- Defined immutable system paths:
  - `/`
  - `/tmp`
  - `/user`
  - `/user/chethan`
  - `/user/chethan/sample.txt`
  - `/user/chethan/wordcount_output`
  - `/user/chethan/wordcount_output/_SUCCESS`
  - `/user/chethan/wordcount_output/part-r-00000`
- Any request (via UI or API) attempting to delete, rename, or overwrite any of these paths or their ancestor directories is blocked immediately with HTTP 403 Forbidden and a clear explanation.

---

## 4. Test Suite Verification Results

The test suite was run via `.venv\Scripts\pytest.exe -v`:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.8, pytest-9.1.1, pluggy-1.7.0 -- C:\hadoop_proj\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\hadoop_proj
collected 42 items

tests/test_config.py::test_base_config_defaults PASSED                   [  2%]
tests/test_config.py::test_config_environments PASSED                    [  4%]
tests/test_hadoop_adapter_unit.py::test_subprocess_timeout_handling PASSED [  7%]
tests/test_hadoop_adapter_unit.py::test_check_wsl_status_offline PASSED  [  9%]
tests/test_hadoop_adapter_unit.py::test_get_namenode_jmx_connection_refused PASSED [ 11%]
tests/test_hadoop_adapter_unit.py::test_get_yarn_cluster_info_500_error PASSED [ 14%]
tests/test_hadoop_adapter_unit.py::test_list_hdfs_directory_fallback_to_cli PASSED [ 16%]
tests/test_hdfs_mutations_live.py::test_live_mkdir_in_sandbox PASSED     [ 19%]
tests/test_hdfs_mutations_live.py::test_live_upload_and_preview_file PASSED [ 21%]
tests/test_hdfs_mutations_live.py::test_live_copy_and_rename_file PASSED [ 23%]
tests/test_hdfs_mutations_live.py::test_live_delete_file_single PASSED   [ 26%]
tests/test_hdfs_mutations_live.py::test_live_delete_directory_confirmation_enforcement PASSED [ 28%]
tests/test_hdfs_mutations_live.py::test_live_protection_guard_sample_txt PASSED [ 30%]
tests/test_hdfs_mutations_live.py::test_live_protection_guard_system_directories PASSED [ 33%]
tests/test_hdfs_mutations_live.py::test_live_file_manager_routes_end_to_end PASSED [ 35%]
tests/test_hdfs_mutations_live.py::test_live_baseline_fidelity_post_mutation PASSED [ 38%]
tests/test_hdfs_service_unit.py::test_sanitize_item_name_valid PASSED    [ 40%]
tests/test_hdfs_service_unit.py::test_sanitize_item_name_rejects_slashes_and_whitespace PASSED [ 42%]
tests/test_hdfs_service_unit.py::test_build_breadcrumbs PASSED           [ 45%]
tests/test_hdfs_service_unit.py::test_get_parent_path PASSED             [ 47%]
tests/test_hdfs_service_unit.py::test_browse_directory_annotates_protected_paths PASSED [ 50%]
tests/test_hdfs_service_unit.py::test_handle_upload_staging_cleanup_on_failure PASSED [ 52%]
tests/test_live_integration.py::test_live_wsl_status PASSED              [ 54%]
tests/test_live_integration.py::test_live_hadoop_cli PASSED              [ 57%]
tests/test_live_integration.py::test_live_jps_processes PASSED           [ 59%]
tests/test_live_integration.py::test_live_namenode_jmx PASSED            [ 61%]
tests/test_live_integration.py::test_live_yarn_cluster_info PASSED       [ 64%]
tests/test_live_integration.py::test_live_hdfs_user_directory_listing PASSED [ 66%]
tests/test_live_integration.py::test_live_sample_text_preview_and_fidelity PASSED [ 69%]
tests/test_live_integration.py::test_live_wordcount_output_unaltered PASSED [ 71%]
tests/test_live_integration.py::test_flask_diagnostics_page_loads PASSED [ 73%]
tests/test_live_integration.py::test_flask_api_diagnostics_endpoint PASSED [ 76%]
tests/test_live_integration.py::test_flask_api_path_traversal_blocked PASSED [ 78%]
tests/test_path_validation.py::test_valid_paths PASSED                   [ 80%]
tests/test_path_validation.py::test_reject_relative_or_empty_paths PASSED [ 83%]
tests/test_path_validation.py::test_reject_path_traversal PASSED         [ 85%]
tests/test_path_validation.py::test_reject_dangerous_characters PASSED   [ 88%]
tests/test_redirect_validation.py::test_normalize_verified_wsl_host PASSED [ 90%]
tests/test_redirect_validation.py::test_preserve_trusted_loopback_hosts PASSED [ 92%]
tests/test_redirect_validation.py::test_reject_untrusted_redirect_hosts PASSED [ 95%]
tests/test_redirect_validation.py::test_reject_invalid_schemes PASSED    [ 97%]
tests/test_redirect_validation.py::test_reject_empty_redirect_url PASSED [100%]

======================== 42 passed in 93.29s (0:01:33) ========================
```

### Direct Cluster State Verification
Post-test verification confirmed the cluster state is completely healthy and unaltered:
- `hdfs dfs -ls /user/chethan`:
  ```text
  -rw-r--r--   1 chethan supergroup         58 2026-10-20 08:00 /user/chethan/sample.txt
  drwxr-xr-x   - chethan supergroup          0 2026-10-20 08:02 /user/chethan/wordcount_output
  ```
- Contents of `/user/chethan/wordcount_output/part-r-00000` (46 bytes) verified identical to baseline.
- Ephemeral sandbox directory (`/user/chethan/phase3_test_sandbox`) was removed completely.

---

## 5. How to Launch and Test

To run the application and test the file manager:

```powershell
# Navigate to project root
cd C:\hadoop_proj

# Run application using the project virtual environment
.\.venv\Scripts\python.exe run.py
```

1. Open your browser and navigate to: **`http://localhost:5000/file-manager`**
2. **Browse:** Click folder links or breadcrumb segments to navigate through HDFS.
3. **Preview:** Click the eye icon next to `sample.txt` to view text content directly from HDFS.
4. **Download:** Click the download icon to save a local copy of any file.
5. **New Folder:** Click "New Folder" in the action toolbar to create a directory.
6. **Upload:** Click "Upload File" to select any local file and upload it into the current directory.
7. **Delete:** Click the trash icon; notice that protected files reject deletion, and directories require typing the directory name to confirm.

To run the automated tests:
```powershell
.\.venv\Scripts\pytest.exe -v
```

---

## 6. Known Limitations

- **Single DataNode Topology:** The pseudo-distributed Hadoop cluster has a single DataNode, so replication defaults to 1.
- **Upload Size Ceiling:** Single-file uploads are currently bounded at 100 MB per request to prevent local memory/disk exhaustion.

---

## 7. Next Steps (Pending Approval)

Phase 3 is complete. In accordance with the instructions, work has stopped here pending user review and approval to proceed to **Phase 4 — Java MapReduce Programs & Compilation Engine** (implementing standalone Java MapReduce jobs for WordCount, Matrix Multiplication, and Weather CSV processing, compiled with OpenJDK 17).
