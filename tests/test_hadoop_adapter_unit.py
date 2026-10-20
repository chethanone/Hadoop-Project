"""
Unit tests for HadoopAdapter using mocks to verify error handling and resilience.
"""
import subprocess
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.app.config import TestingConfig
from src.app.services.hadoop_adapter import HadoopAdapter, HadoopExecutionError


@pytest.fixture
def mock_adapter():
    config = TestingConfig()
    return HadoopAdapter(config=config)


def test_subprocess_timeout_handling(mock_adapter):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="wsl.exe", timeout=2)):
        with pytest.raises(HadoopExecutionError, match="timed out"):
            mock_adapter.run_wsl_command(["sleep", "10"], timeout=2)


def test_check_wsl_status_offline(mock_adapter):
    with patch("subprocess.run", side_effect=FileNotFoundError("wsl.exe not found")):
        status = mock_adapter.check_wsl_status()
        assert status["status"] == "Offline"
        assert "not found" in status["error"]


def test_get_namenode_jmx_connection_refused(mock_adapter):
    with patch.object(mock_adapter.session, "get", side_effect=requests.ConnectionError("Connection refused")):
        res = mock_adapter.get_namenode_jmx()
        assert res["status"] == "Offline"
        assert "Failed to connect" in res["error"]


def test_get_yarn_cluster_info_500_error(mock_adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch.object(mock_adapter.session, "get", return_value=mock_resp):
        res = mock_adapter.get_yarn_cluster_info()
        assert res["status"] == "Error"
        assert "HTTP 500" in res["error"]


def test_list_hdfs_directory_fallback_to_cli(mock_adapter):
    # WebHDFS fails with connection error, CLI succeeds
    cli_output = (
        "Found 2 items\n"
        "-rw-r--r--   1 chethan supergroup         58 2026-10-20 08:00 /user/chethan/sample.txt\n"
        "drwxr-xr-x   - chethan supergroup          0 2026-10-20 08:02 /user/chethan/wordcount_output\n"
    )
    with patch.object(mock_adapter.session, "get", side_effect=requests.ConnectionError("WebHDFS down")), \
         patch.object(mock_adapter, "run_wsl_command", return_value=(0, cli_output, "")):
        res = mock_adapter.list_hdfs_directory("/user/chethan")
        assert res["status"] == "Online"
        assert res["source"] == "CLI"
        assert res["total_count"] == 2
        names = [e["name"] for e in res["entries"]]
        assert "sample.txt" in names
        assert "wordcount_output" in names
