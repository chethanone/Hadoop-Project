"""
Unit tests for HdfsService business logic, breadcrumbs, sanitization, and upload staging.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.app.config import TestingConfig
from src.app.services.hadoop_adapter import HadoopPathError, ProtectedPathError
from src.app.services.hdfs_service import HdfsService


@pytest.fixture
def hdfs_service():
    config = TestingConfig()
    adapter = MagicMock()
    adapter.sanitize_hdfs_path.side_effect = lambda p: "/" + "/".join(part for part in p.split("/") if part) if p != "/" else "/"
    return HdfsService(adapter=adapter, config=config)


def test_sanitize_item_name_valid(hdfs_service):
    assert hdfs_service.sanitize_item_name("sample.txt") == "sample.txt"
    assert hdfs_service.sanitize_item_name("my_data-2026.csv") == "my_data-2026.csv"
    assert hdfs_service.sanitize_item_name("folder_1") == "folder_1"


def test_sanitize_item_name_rejects_slashes_and_whitespace(hdfs_service):
    invalid_names = [
        "folder/subfolder",
        "file\\name",
        "name with space",
        "..",
        ".",
        "",
        "file\nname",
        "name;rm"
    ]
    for name in invalid_names:
        with pytest.raises(HadoopPathError):
            hdfs_service.sanitize_item_name(name)


def test_build_breadcrumbs(hdfs_service):
    crumbs = hdfs_service.build_breadcrumbs("/user/chethan/docs")
    assert len(crumbs) == 4
    assert crumbs[0]["name"] == "Root (/)" and crumbs[0]["path"] == "/"
    assert crumbs[1]["name"] == "user" and crumbs[1]["path"] == "/user"
    assert crumbs[2]["name"] == "chethan" and crumbs[2]["path"] == "/user/chethan"
    assert crumbs[3]["name"] == "docs" and crumbs[3]["path"] == "/user/chethan/docs"
    assert crumbs[3]["active"] is True


def test_get_parent_path(hdfs_service):
    assert hdfs_service.get_parent_path("/") == "/"
    assert hdfs_service.get_parent_path("/user") == "/"
    assert hdfs_service.get_parent_path("/user/chethan") == "/user"
    assert hdfs_service.get_parent_path("/user/chethan/data") == "/user/chethan"


def test_browse_directory_annotates_protected_paths(hdfs_service):
    hdfs_service.adapter.list_hdfs_directory.return_value = {
        "status": "Online",
        "entries": [
            {"name": "sample.txt", "path": "/user/chethan/sample.txt", "type": "FILE"},
            {"name": "my_sandbox", "path": "/user/chethan/my_sandbox", "type": "DIRECTORY"}
        ],
        "source": "WebHDFS"
    }

    result = hdfs_service.browse_directory("/user/chethan")
    entries = result["entries"]
    assert len(entries) == 2

    # sample.txt is in PROTECTED_HDFS_PATHS
    sample_entry = next(e for e in entries if e["name"] == "sample.txt")
    assert sample_entry["is_protected"] is True

    # my_sandbox is not in PROTECTED_HDFS_PATHS
    sandbox_entry = next(e for e in entries if e["name"] == "my_sandbox")
    assert sandbox_entry["is_protected"] is False


def test_handle_upload_staging_cleanup_on_failure(hdfs_service, tmp_path):
    hdfs_service.config.TEMP_STAGING_DIR = tmp_path
    mock_file = MagicMock()
    mock_file.filename = "test_upload.txt"
    mock_file.save.side_effect = lambda dst: Path(dst).write_text("sample content")

    # Simulate adapter put_file failure
    hdfs_service.adapter.put_file.side_effect = RuntimeError("HDFS write failure")

    with pytest.raises(RuntimeError, match="HDFS write failure"):
        hdfs_service.handle_upload(mock_file, "/user/chethan")

    # Staged file should have been cleaned up in finally block
    staged_files = list(tmp_path.glob("*test_upload.txt"))
    assert len(staged_files) == 0, "Staged file was not cleaned up after failure"
