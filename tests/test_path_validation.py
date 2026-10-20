"""
Unit tests for HDFS path validation and sanitization.
Ensures path traversal and injection vectors are strictly blocked.
"""
import pytest
from src.app.services.hadoop_adapter import HadoopAdapter, HadoopPathError


def test_valid_paths():
    assert HadoopAdapter.sanitize_hdfs_path("/") == "/"
    assert HadoopAdapter.sanitize_hdfs_path("/user/chethan") == "/user/chethan"
    assert HadoopAdapter.sanitize_hdfs_path("/user/chethan/sample.txt") == "/user/chethan/sample.txt"
    # Redundant slashes should be normalized
    assert HadoopAdapter.sanitize_hdfs_path("//user///chethan//") == "/user/chethan"


def test_reject_relative_or_empty_paths():
    with pytest.raises(HadoopPathError, match="cannot be empty"):
        HadoopAdapter.sanitize_hdfs_path("")

    with pytest.raises(HadoopPathError, match="must be absolute"):
        HadoopAdapter.sanitize_hdfs_path("user/chethan")

    with pytest.raises(HadoopPathError, match="must be absolute"):
        HadoopAdapter.sanitize_hdfs_path("sample.txt")


def test_reject_path_traversal():
    traversal_vectors = [
        "/../",
        "/user/../etc/passwd",
        "/user/chethan/..",
        "/user/./chethan",
        "/a/b/../../c"
    ]
    for vector in traversal_vectors:
        with pytest.raises(HadoopPathError, match="Directory traversal"):
            HadoopAdapter.sanitize_hdfs_path(vector)


def test_reject_dangerous_characters():
    injection_vectors = [
        "/user/chethan; rm -rf /",
        "/user/chethan | cat /etc/shadow",
        "/user/chethan`whoami`",
        "/user/chethan$(id)",
        "/user/chethan&calc.exe",
        "/user/chethan\x00evil",
        "/user/chethan\nevil",
        "/user/chethan\\windows\\path",
        "/user/chethan*wildcard"
    ]
    for vector in injection_vectors:
        with pytest.raises(HadoopPathError, match="illegal or dangerous characters"):
            HadoopAdapter.sanitize_hdfs_path(vector)
