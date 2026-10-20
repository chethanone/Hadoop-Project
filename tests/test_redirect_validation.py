"""
Unit tests for WebHDFS redirect host validation and normalization.
Ensures SSRF protection and accurate hostname rewriting.
"""
import pytest
from src.app.services.hadoop_adapter import HadoopAdapter, HadoopRedirectError


@pytest.fixture
def adapter():
    return HadoopAdapter()


def test_normalize_verified_wsl_host(adapter):
    input_url = "http://Astro.localdomain:9864/webhdfs/v1/user/chethan/sample.txt?op=OPEN&offset=0"
    normalized = adapter.validate_and_normalize_redirect_url(input_url)
    assert normalized.startswith("http://127.0.0.1:9864/webhdfs/v1/user/chethan/sample.txt")
    assert "op=OPEN" in normalized


def test_preserve_trusted_loopback_hosts(adapter):
    input_local = "http://localhost:9864/webhdfs/v1/file?op=OPEN"
    normalized_local = adapter.validate_and_normalize_redirect_url(input_local)
    assert normalized_local == input_local

    input_ip = "http://127.0.0.1:9864/webhdfs/v1/file?op=OPEN"
    normalized_ip = adapter.validate_and_normalize_redirect_url(input_ip)
    assert normalized_ip == input_ip


def test_reject_untrusted_redirect_hosts(adapter):
    untrusted_urls = [
        "http://evil.com/webhdfs/v1/user/chethan/sample.txt?op=OPEN",
        "http://192.168.1.50:9864/webhdfs/v1/file?op=OPEN",
        "http://169.254.169.254/latest/meta-data",
        "http://attacker.localdomain:9864/file"
    ]
    for url in untrusted_urls:
        with pytest.raises(HadoopRedirectError, match="Untrusted redirect host"):
            adapter.validate_and_normalize_redirect_url(url)


def test_reject_invalid_schemes(adapter):
    invalid_schemes = [
        "ftp://Astro.localdomain:9864/file",
        "file:///etc/passwd",
        "gopher://Astro.localdomain:9864/",
        "javascript:alert(1)"
    ]
    for url in invalid_schemes:
        with pytest.raises(HadoopRedirectError, match="Prohibited redirect scheme"):
            adapter.validate_and_normalize_redirect_url(url)


def test_reject_empty_redirect_url(adapter):
    with pytest.raises(HadoopRedirectError, match="Empty redirect URL"):
        adapter.validate_and_normalize_redirect_url("")
