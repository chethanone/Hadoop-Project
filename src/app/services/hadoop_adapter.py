"""
Hadoop Adapter Service.
Provides a hardened, secure bridge between the Windows Flask application
and the WSL2-hosted Apache Hadoop 3.5.0 cluster.
"""

import logging
import os
import re
import subprocess
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..config import Config

logger = logging.getLogger(__name__)


class HadoopError(Exception):
    """Base exception for all Hadoop adapter operations."""
    pass


class HadoopPathError(HadoopError):
    """Raised when an HDFS path fails security validation."""
    pass


class HadoopExecutionError(HadoopError):
    """Raised when a subprocess command fails or exits non-zero."""
    def __init__(self, message: str, exit_code: Optional[int] = None, stdout: str = "", stderr: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class HadoopRedirectError(HadoopError):
    """Raised when a WebHDFS redirect points to an untrusted host or scheme."""
    pass


class HadoopAdapter:
    """
    Secure adapter for invoking Hadoop operations in WSL and querying
    HDFS / YARN HTTP and REST endpoints.
    """

    # Forbidden shell metacharacters and path traversal patterns
    ILLEGAL_PATH_CHARS = re.compile(r'[\x00-\x1f\x7f;`$&|<>\t\r\n\\~*?]')

    def __init__(self, config: Optional[Any] = None):
        if config is None:
            self.config = Config()
        elif hasattr(config, "WSL_DISTRO"):
            self.config = config
        else:
            # Fallback if a dict or Flask Config object was provided
            self.config = Config()
            if hasattr(config, "items"):
                for k, v in config.items():
                    if hasattr(self.config, k):
                        setattr(self.config, k, v)
            elif hasattr(config, "__getitem__"):
                for k in dir(self.config):
                    if k.isupper() and k in config:
                        setattr(self.config, k, config[k])
        self.session = requests.Session()

    # -------------------------------------------------------------------------
    # Security & Path Validation
    # -------------------------------------------------------------------------

    @classmethod
    def sanitize_hdfs_path(cls, path: str) -> str:
        """
        Validates and canonicalizes an HDFS path.
        Enforces:
        - Must be a non-empty string.
        - Must begin with a forward slash '/'.
        - Must NOT contain directory traversal sequences ('..').
        - Must NOT contain shell metacharacters or control characters.
        """
        if not path or not isinstance(path, str):
            raise HadoopPathError("HDFS path cannot be empty or non-string.")

        path = path.strip()

        if not path.startswith("/"):
            raise HadoopPathError(f"HDFS path must be absolute and start with '/': {path}")

        if cls.ILLEGAL_PATH_CHARS.search(path):
            raise HadoopPathError(f"HDFS path contains illegal or dangerous characters: {path}")

        # Check for path traversal sequences like /../ or ending with /..
        parts = path.split("/")
        for part in parts:
            if part in ("..", "."):
                raise HadoopPathError(f"Directory traversal sequences are prohibited in HDFS path: {path}")

        # Normalize redundant slashes (e.g. '//user///chethan' -> '/user/chethan')
        normalized = "/" + "/".join(p for p in parts if p)
        return normalized

    def validate_and_normalize_redirect_url(self, redirect_url: str) -> str:
        """
        Validates a WebHDFS redirect URL and normalizes verified WSL hostnames
        to trusted loopback address (127.0.0.1).
        Rejects non-HTTP schemes and unauthorized hosts to prevent SSRF.
        """
        if not redirect_url:
            raise HadoopRedirectError("Empty redirect URL received from WebHDFS.")

        parsed = urllib.parse.urlparse(redirect_url)

        if parsed.scheme not in ("http", "https"):
            raise HadoopRedirectError(f"Prohibited redirect scheme: {parsed.scheme}")

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise HadoopRedirectError(f"Missing hostname in redirect URL: {redirect_url}")

        if hostname not in self.config.ALLOWED_REDIRECT_HOSTS:
            raise HadoopRedirectError(
                f"Untrusted redirect host '{hostname}'. Allowed hosts: {self.config.ALLOWED_REDIRECT_HOSTS}"
            )

        # Apply rewrite for verified WSL internal hostname
        target_host = self.config.REDIRECT_REWRITE_MAP.get(hostname, hostname)
        port_suffix = f":{parsed.port}" if parsed.port else ""
        netloc = f"{target_host}{port_suffix}"

        normalized_url = urllib.parse.urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        return normalized_url

    # -------------------------------------------------------------------------
    # Safe WSL Subprocess Execution
    # -------------------------------------------------------------------------

    def run_wsl_command(
        self,
        command_args: List[str],
        timeout: Optional[int] = None
    ) -> Tuple[int, str, str]:
        """
        Executes a command inside the configured WSL distribution using
        explicit token lists with shell=False.
        """
        timeout = timeout or self.config.SUBPROCESS_TIMEOUT_SECONDS
        full_command = ["wsl.exe", "-d", self.config.WSL_DISTRO, "--"] + command_args

        logger.debug("Executing WSL command: %s", full_command)

        try:
            start_time = time.time()
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.debug("WSL command finished in %d ms with exit code %d", elapsed_ms, result.returncode)
            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired as exc:
            msg = f"WSL command timed out after {timeout} seconds: {' '.join(command_args)}"
            logger.error(msg)
            raise HadoopExecutionError(msg) from exc
        except FileNotFoundError as exc:
            msg = "wsl.exe was not found on the host system PATH."
            logger.error(msg)
            raise HadoopExecutionError(msg) from exc
        except Exception as exc:
            msg = f"Unexpected error executing WSL command: {str(exc)}"
            logger.exception(msg)
            raise HadoopExecutionError(msg) from exc

    # -------------------------------------------------------------------------
    # Diagnostics & Status Checks
    # -------------------------------------------------------------------------

    def check_wsl_status(self) -> Dict[str, Any]:
        """Verifies WSL Ubuntu responsiveness and kernel info."""
        try:
            code, stdout, stderr = self.run_wsl_command(["uname", "-srmo"], timeout=5)
            if code == 0:
                return {
                    "status": "Online",
                    "details": stdout.strip(),
                    "distro": self.config.WSL_DISTRO,
                    "error": None
                }
            return {
                "status": "Error",
                "details": f"Command exited with code {code}",
                "distro": self.config.WSL_DISTRO,
                "error": stderr.strip() or stdout.strip()
            }
        except Exception as exc:
            return {
                "status": "Offline",
                "details": "Failed to communicate with WSL subsystem.",
                "distro": self.config.WSL_DISTRO,
                "error": str(exc)
            }

    def check_hadoop_cli(self) -> Dict[str, Any]:
        """Verifies Hadoop CLI availability in WSL."""
        try:
            code, stdout, stderr = self.run_wsl_command([self.config.HDFS_BIN_WSL, "version"], timeout=8)
            if code == 0:
                # Extract first two lines of version output
                lines = [line.strip() for line in stdout.splitlines() if line.strip()]
                version_summary = " - ".join(lines[:2]) if lines else "Hadoop 3.x"
                return {
                    "status": "Online",
                    "version": version_summary,
                    "raw": stdout.strip(),
                    "error": None
                }
            return {
                "status": "Error",
                "version": "Unavailable",
                "raw": stdout.strip(),
                "error": stderr.strip() or f"Exit code {code}"
            }
        except Exception as exc:
            return {
                "status": "Offline",
                "version": "Unavailable",
                "raw": "",
                "error": str(exc)
            }

    def check_jps_processes(self) -> Dict[str, Any]:
        """Queries running Java processes in WSL via `jps -l`."""
        try:
            code, stdout, stderr = self.run_wsl_command(["jps", "-l"], timeout=6)
            if code == 0:
                processes = []
                for line in stdout.splitlines():
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) == 2:
                        pid, name = parts
                        processes.append({"pid": pid, "name": name})
                    elif len(parts) == 1:
                        processes.append({"pid": parts[0], "name": "Unknown"})

                required_daemons = ["NameNode", "DataNode", "SecondaryNameNode", "ResourceManager", "NodeManager"]
                detected_names = [p["name"] for p in processes]
                missing_daemons = [d for d in required_daemons if not any(d in name for name in detected_names)]

                return {
                    "status": "Online" if not missing_daemons else ("Degraded" if processes else "Offline"),
                    "processes": processes,
                    "missing_daemons": missing_daemons,
                    "error": None
                }
            return {
                "status": "Error",
                "processes": [],
                "missing_daemons": [],
                "error": stderr.strip() or f"Exit code {code}"
            }
        except Exception as exc:
            return {
                "status": "Offline",
                "processes": [],
                "missing_daemons": [],
                "error": str(exc)
            }

    def get_namenode_jmx(self) -> Dict[str, Any]:
        """Queries NameNode JMX endpoint for HDFS state and capacity."""
        url = self.config.NAMENODE_JMX_URL
        try:
            resp = self.session.get(url, timeout=self.config.HTTP_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                data = resp.json()
                beans = data.get("beans", [])

                # Extract FSNamesystemState bean
                fs_state = next(
                    (b for b in beans if b.get("name") == "Hadoop:service=NameNode,name=FSNamesystemState"),
                    {}
                )
                fs_info = next(
                    (b for b in beans if b.get("name") == "Hadoop:service=NameNode,name=FSNamesystem"),
                    {}
                )

                capacity_total = fs_state.get("CapacityTotal", 0)
                capacity_used = fs_state.get("CapacityUsed", 0)
                capacity_remaining = fs_state.get("CapacityRemaining", 0)
                files_total = fs_state.get("FilesTotal", 0)
                blocks_total = fs_state.get("BlocksTotal", 0)
                num_live_datanodes = fs_state.get("NumLiveDataNodes", 0)
                num_dead_datanodes = fs_state.get("NumDeadDataNodes", 0)
                fs_operational_state = fs_state.get("FSState", "Operational")

                return {
                    "status": "Online",
                    "http_status": resp.status_code,
                    "fs_state": fs_operational_state,
                    "capacity_total": capacity_total,
                    "capacity_used": capacity_used,
                    "capacity_remaining": capacity_remaining,
                    "files_total": files_total,
                    "blocks_total": blocks_total,
                    "num_live_datanodes": num_live_datanodes,
                    "num_dead_datanodes": num_dead_datanodes,
                    "corrupt_blocks": fs_info.get("CorruptBlocks", 0),
                    "missing_blocks": fs_info.get("MissingBlocks", 0),
                    "error": None
                }
            return {
                "status": "Error",
                "http_status": resp.status_code,
                "error": f"NameNode JMX returned HTTP {resp.status_code}"
            }
        except requests.RequestException as exc:
            return {
                "status": "Offline",
                "http_status": None,
                "error": f"Failed to connect to NameNode JMX at {url}: {str(exc)}"
            }

    def check_datanode_status(self) -> Dict[str, Any]:
        """Checks DataNode HTTP web port reachability."""
        url = self.config.DATANODE_HTTP_URL
        try:
            resp = self.session.get(url, timeout=self.config.HTTP_TIMEOUT_SECONDS)
            # DataNode web port responds with 200 or 302
            if resp.status_code in (200, 302):
                return {
                    "status": "Online",
                    "http_status": resp.status_code,
                    "url": url,
                    "error": None
                }
            return {
                "status": "Error",
                "http_status": resp.status_code,
                "url": url,
                "error": f"Unexpected HTTP {resp.status_code}"
            }
        except requests.RequestException as exc:
            return {
                "status": "Offline",
                "http_status": None,
                "url": url,
                "error": f"DataNode web endpoint unreachable at {url}: {str(exc)}"
            }

    def get_yarn_cluster_info(self) -> Dict[str, Any]:
        """Queries YARN ResourceManager cluster info via REST API."""
        url = self.config.YARN_CLUSTER_INFO_URL
        try:
            resp = self.session.get(url, timeout=self.config.HTTP_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                data = resp.json().get("clusterInfo", {})
                return {
                    "status": "Online",
                    "http_status": resp.status_code,
                    "cluster_id": data.get("id"),
                    "ha_state": data.get("haState"),
                    "state": data.get("state"),
                    "hadoop_version": data.get("hadoopVersion"),
                    "started_time": data.get("startedOn"),
                    "error": None
                }
            return {
                "status": "Error",
                "http_status": resp.status_code,
                "error": f"YARN RM returned HTTP {resp.status_code}"
            }
        except requests.RequestException as exc:
            return {
                "status": "Offline",
                "http_status": None,
                "error": f"YARN ResourceManager unreachable at {url}: {str(exc)}"
            }

    def get_yarn_cluster_metrics(self) -> Dict[str, Any]:
        """Queries YARN ResourceManager cluster metrics (apps, memory, containers)."""
        url = self.config.YARN_CLUSTER_METRICS_URL
        try:
            resp = self.session.get(url, timeout=self.config.HTTP_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                metrics = resp.json().get("clusterMetrics", {})
                return {
                    "status": "Online",
                    "apps_submitted": metrics.get("appsSubmitted", 0),
                    "apps_completed": metrics.get("appsCompleted", 0),
                    "apps_running": metrics.get("appsRunning", 0),
                    "apps_failed": metrics.get("appsFailed", 0),
                    "containers_allocated": metrics.get("containersAllocated", 0),
                    "allocated_mb": metrics.get("allocatedMB", 0),
                    "available_mb": metrics.get("availableMB", 0),
                    "error": None
                }
            return {"status": "Error", "error": f"HTTP {resp.status_code}"}
        except requests.RequestException as exc:
            return {"status": "Offline", "error": str(exc)}

    def get_yarn_apps(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Queries recent YARN applications."""
        url = f"{self.config.YARN_CLUSTER_APPS_URL}?limit={limit}"
        try:
            resp = self.session.get(url, timeout=self.config.HTTP_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                apps_data = resp.json().get("apps")
                if apps_data and "app" in apps_data:
                    return apps_data["app"]
                return []
            return []
        except requests.RequestException as exc:
            logger.warning("Failed to fetch YARN applications: %s", exc)
            return []

    # -------------------------------------------------------------------------
    # HDFS File & Directory Read Operations
    # -------------------------------------------------------------------------

    def list_hdfs_directory(self, path: str = "/") -> Dict[str, Any]:
        """
        Lists directory contents in HDFS.
        Primary strategy: WebHDFS LISTSTATUS.
        Fallback strategy: Safe wsl.exe CLI execution ('hdfs dfs -ls').
        """
        sanitized_path = self.sanitize_hdfs_path(path)

        # 1. Attempt WebHDFS LISTSTATUS
        webhdfs_url = f"{self.config.NAMENODE_HTTP_URL}/webhdfs/v1{sanitized_path}?op=LISTSTATUS"
        try:
            resp = self.session.get(webhdfs_url, timeout=self.config.HTTP_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                payload = resp.json()
                statuses = payload.get("FileStatuses", {}).get("FileStatus", [])

                entries = []
                for item in statuses:
                    suffix = item.get("pathSuffix", "")
                    item_path = f"{sanitized_path.rstrip('/')}/{suffix}" if suffix else sanitized_path
                    mod_epoch = item.get("modificationTime", 0) / 1000.0
                    mod_dt = datetime.fromtimestamp(mod_epoch).strftime("%Y-%m-%d %H:%M:%S") if mod_epoch else "Unknown"

                    entries.append({
                        "name": suffix or os.path.basename(sanitized_path),
                        "path": item_path,
                        "type": item.get("type"),  # "FILE" or "DIRECTORY"
                        "length": item.get("length", 0),
                        "owner": item.get("owner", ""),
                        "group": item.get("group", ""),
                        "permission": item.get("permission", ""),
                        "replication": item.get("replication", 0),
                        "modification_time": mod_dt,
                        "raw_timestamp": item.get("modificationTime", 0)
                    })

                # Sort directories first, then alphabetical by name
                entries.sort(key=lambda x: (0 if x["type"] == "DIRECTORY" else 1, x["name"].lower()))

                return {
                    "status": "Online",
                    "path": sanitized_path,
                    "entries": entries,
                    "total_count": len(entries),
                    "source": "WebHDFS",
                    "error": None
                }
            elif resp.status_code == 404:
                return {
                    "status": "Error",
                    "path": sanitized_path,
                    "entries": [],
                    "total_count": 0,
                    "source": "WebHDFS",
                    "error": f"Directory not found in HDFS: {sanitized_path}"
                }
        except requests.RequestException as exc:
            logger.warning("WebHDFS LISTSTATUS failed (%s), attempting CLI fallback...", exc)

        # 2. Fallback: Safe CLI Subprocess Execution
        try:
            code, stdout, stderr = self.run_wsl_command([
                self.config.HDFS_BIN_WSL, "dfs", "-ls", sanitized_path
            ])
            if code == 0:
                entries = []
                for line in stdout.splitlines():
                    line = line.strip()
                    if not line or line.startswith("Found"):
                        continue
                    parts = line.split()
                    if len(parts) >= 8:
                        perm = parts[0]
                        rep = parts[1]
                        owner = parts[2]
                        group = parts[3]
                        length = int(parts[4]) if parts[4].isdigit() else 0
                        date_str = f"{parts[5]} {parts[6]}"
                        full_item_path = parts[7]
                        is_dir = perm.startswith("d")

                        entries.append({
                            "name": os.path.basename(full_item_path),
                            "path": full_item_path,
                            "type": "DIRECTORY" if is_dir else "FILE",
                            "length": length,
                            "owner": owner,
                            "group": group,
                            "permission": perm,
                            "replication": int(rep) if rep.isdigit() else 0,
                            "modification_time": date_str,
                            "raw_timestamp": 0
                        })

                entries.sort(key=lambda x: (0 if x["type"] == "DIRECTORY" else 1, x["name"].lower()))
                return {
                    "status": "Online",
                    "path": sanitized_path,
                    "entries": entries,
                    "total_count": len(entries),
                    "source": "CLI",
                    "error": None
                }
            return {
                "status": "Error",
                "path": sanitized_path,
                "entries": [],
                "total_count": 0,
                "source": "CLI",
                "error": stderr.strip() or f"CLI returned code {code}"
            }
        except Exception as exc:
            return {
                "status": "Offline",
                "path": sanitized_path,
                "entries": [],
                "total_count": 0,
                "source": "None",
                "error": f"Failed to list directory: {str(exc)}"
            }

    def preview_hdfs_file(
        self,
        path: str,
        max_bytes: Optional[int] = None,
        max_lines: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Safely reads a text preview of an HDFS file.
        Enforces byte and line limits. Handles 307 redirects safely.
        """
        sanitized_path = self.sanitize_hdfs_path(path)
        max_bytes = min(max_bytes or self.config.MAX_PREVIEW_BYTES, self.config.MAX_PREVIEW_BYTES)
        max_lines = min(max_lines or self.config.MAX_PREVIEW_LINES, self.config.MAX_PREVIEW_LINES)

        # 1. Attempt WebHDFS OPEN with redirect host rewrite
        webhdfs_url = f"{self.config.NAMENODE_HTTP_URL}/webhdfs/v1{sanitized_path}?op=OPEN"
        try:
            # Step A: Request NameNode for location (prevent auto-redirect to unresolvable host)
            redirect_resp = self.session.get(
                webhdfs_url,
                allow_redirects=False,
                timeout=self.config.HTTP_TIMEOUT_SECONDS
            )

            if redirect_resp.status_code in (301, 302, 307):
                raw_location = redirect_resp.headers.get("Location")
                normalized_location = self.validate_and_normalize_redirect_url(raw_location)

                # Step B: Stream content from normalized DataNode endpoint
                data_resp = self.session.get(
                    normalized_location,
                    stream=True,
                    timeout=self.config.HTTP_TIMEOUT_SECONDS
                )
                if data_resp.status_code == 200:
                    raw_content = b""
                    for chunk in data_resp.iter_content(chunk_size=8192):
                        raw_content += chunk
                        if len(raw_content) >= max_bytes:
                            break

                    truncated = len(raw_content) >= max_bytes
                    text_content = raw_content.decode("utf-8", errors="replace")
                    lines = text_content.splitlines()

                    if len(lines) > max_lines:
                        lines = lines[:max_lines]
                        truncated = True

                    return {
                        "status": "Online",
                        "path": sanitized_path,
                        "content": "\n".join(lines),
                        "bytes_read": len(raw_content),
                        "line_count": len(lines),
                        "truncated": truncated,
                        "source": "WebHDFS",
                        "error": None
                    }

        except Exception as exc:
            logger.warning("WebHDFS preview failed (%s), attempting safe CLI fallback...", exc)

        # 2. Fallback: Safe CLI cat execution
        try:
            code, stdout, stderr = self.run_wsl_command([
                self.config.HDFS_BIN_WSL, "dfs", "-cat", sanitized_path
            ], timeout=10)
            if code == 0:
                lines = stdout.splitlines()
                truncated = False
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    truncated = True

                content = "\n".join(lines)
                if len(content.encode("utf-8")) > max_bytes:
                    content = content.encode("utf-8")[:max_bytes].decode("utf-8", errors="replace")
                    truncated = True

                return {
                    "status": "Online",
                    "path": sanitized_path,
                    "content": content,
                    "bytes_read": len(content.encode("utf-8")),
                    "line_count": len(lines),
                    "truncated": truncated,
                    "source": "CLI",
                    "error": None
                }
            return {
                "status": "Error",
                "path": sanitized_path,
                "content": "",
                "bytes_read": 0,
                "line_count": 0,
                "truncated": False,
                "source": "CLI",
                "error": stderr.strip() or f"CLI returned code {code}"
            }
        except Exception as exc:
            return {
                "status": "Offline",
                "path": sanitized_path,
                "content": "",
                "bytes_read": 0,
                "line_count": 0,
                "truncated": False,
                "source": "None",
                "error": f"Failed to preview file: {str(exc)}"
            }

    # -------------------------------------------------------------------------
    # Comprehensive Diagnostics Engine
    # -------------------------------------------------------------------------

    def run_full_diagnostics(self) -> Dict[str, Any]:
        """
        Executes a complete sweep of all Hadoop and host subsystems.
        Returns granular status indicators and remediation guidance.
        """
        results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "host_os": "Windows (x86_64)",
            "python_version": os.sys.version.split()[0],
            "wsl": self.check_wsl_status(),
            "hadoop_cli": self.check_hadoop_cli(),
            "jps": self.check_jps_processes(),
            "namenode_jmx": self.get_namenode_jmx(),
            "datanode_web": self.check_datanode_status(),
            "yarn_rm": self.get_yarn_cluster_info(),
            "yarn_metrics": self.get_yarn_cluster_metrics(),
            "hdfs_root": self.list_hdfs_directory("/"),
            "hdfs_user": self.list_hdfs_directory(self.config.DEFAULT_HDFS_USER_DIR),
            "remediation": []
        }

        # Build active remediation recommendations if any subsystem is offline
        if results["wsl"]["status"] != "Online":
            results["remediation"].append({
                "subsystem": "WSL2 Subsystem",
                "issue": "Ubuntu distribution is stopped or unresponsive.",
                "action": "Open PowerShell and run: `wsl -d Ubuntu` or `wsl --status`"
            })

        if results["namenode_jmx"]["status"] != "Online":
            results["remediation"].append({
                "subsystem": "HDFS NameNode",
                "issue": "NameNode JMX is offline at port 9870.",
                "action": "Inside WSL Ubuntu, execute: `start-dfs.sh` or `$HADOOP_HOME/bin/hdfs --daemon start namenode`"
            })

        if results["datanode_web"]["status"] != "Online":
            results["remediation"].append({
                "subsystem": "HDFS DataNode",
                "issue": "DataNode HTTP port 9864 is unreachable.",
                "action": "Inside WSL Ubuntu, execute: `$HADOOP_HOME/bin/hdfs --daemon start datanode`"
            })

        if results["yarn_rm"]["status"] != "Online":
            results["remediation"].append({
                "subsystem": "YARN ResourceManager",
                "issue": "ResourceManager REST API is offline at port 8088.",
                "action": "Inside WSL Ubuntu, execute: `start-yarn.sh` or `$HADOOP_HOME/bin/yarn --daemon start resourcemanager`"
            })

        return results
