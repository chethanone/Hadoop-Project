"""
Live Integration Tests against the active WSL2 Hadoop 3.5.0 cluster.
Verifies real HDFS connectivity, NameNode JMX, YARN REST API, and data fidelity.
"""
import pytest
from src.app import create_app
from src.app.services.hadoop_adapter import HadoopAdapter, HadoopPathError


@pytest.fixture(scope="module")
def live_adapter():
    return HadoopAdapter()


@pytest.fixture(scope="module")
def test_client():
    app = create_app("testing")
    with app.test_client() as client:
        yield client


def test_live_wsl_status(live_adapter):
    res = live_adapter.check_wsl_status()
    assert res["status"] == "Online", f"WSL check failed: {res.get('error')}"
    assert "Linux" in res["details"]


def test_live_hadoop_cli(live_adapter):
    res = live_adapter.check_hadoop_cli()
    assert res["status"] == "Online", f"Hadoop CLI check failed: {res.get('error')}"
    assert "Hadoop 3.5.0" in res["raw"] or "Hadoop" in res["version"]


def test_live_jps_processes(live_adapter):
    res = live_adapter.check_jps_processes()
    assert res["status"] in ("Online", "Degraded"), f"JPS check failed: {res.get('error')}"
    names = [p["name"] for p in res["processes"]]
    assert any("NameNode" in n for n in names), "NameNode not detected in live jps"
    assert any("DataNode" in n for n in names), "DataNode not detected in live jps"
    assert any("ResourceManager" in n for n in names), "ResourceManager not detected in live jps"


def test_live_namenode_jmx(live_adapter):
    res = live_adapter.get_namenode_jmx()
    assert res["status"] == "Online", f"NameNode JMX failed: {res.get('error')}"
    assert res["capacity_total"] > 0
    assert res["files_total"] >= 23
    assert res["num_live_datanodes"] >= 1
    assert res["fs_state"] == "Operational"


def test_live_yarn_cluster_info(live_adapter):
    res = live_adapter.get_yarn_cluster_info()
    assert res["status"] == "Online", f"YARN RM check failed: {res.get('error')}"
    assert res["state"] == "STARTED" or res["state"] is not None
    assert res["hadoop_version"] is not None


def test_live_hdfs_user_directory_listing(live_adapter):
    """Verifies that /user/chethan contains the verified existing sample files."""
    res = live_adapter.list_hdfs_directory("/user/chethan")
    assert res["status"] == "Online", f"Listing /user/chethan failed: {res.get('error')}"
    names = [item["name"] for item in res["entries"]]
    assert "sample.txt" in names, "sample.txt missing from /user/chethan"
    assert "wordcount_output" in names, "wordcount_output directory missing from /user/chethan"


def test_live_sample_text_preview_and_fidelity(live_adapter):
    """
    Verifies that sample.txt can be read via normalized WebHDFS/CLI
    and that its known content remains 100% unaltered.
    """
    res = live_adapter.preview_hdfs_file("/user/chethan/sample.txt")
    assert res["status"] == "Online", f"Preview failed: {res.get('error')}"
    expected_lines = [
        "hadoop is powerful",
        "hadoop is useful",
        "mapreduce is powerful"
    ]
    content = res["content"].strip()
    for line in expected_lines:
        assert line in content, f"Expected line '{line}' missing from sample.txt content"
    assert res["bytes_read"] == 58


def test_live_wordcount_output_unaltered(live_adapter):
    """
    Verifies that the previously completed WordCount job output
    at /user/chethan/wordcount_output/part-r-00000 remains completely intact.
    """
    res = live_adapter.preview_hdfs_file("/user/chethan/wordcount_output/part-r-00000")
    assert res["status"] == "Online", f"Wordcount output preview failed: {res.get('error')}"
    content = res["content"]
    assert "hadoop\t2" in content
    assert "is\t3" in content
    assert "mapreduce\t1" in content
    assert "powerful\t2" in content
    assert "useful\t1" in content


def test_flask_diagnostics_page_loads(test_client):
    """Verifies that the Flask diagnostics endpoint renders successfully with HTTP 200."""
    response = test_client.get("/diagnostics")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "System Diagnostics & Cluster Health" in html
    assert "NameNode" in html
    assert "ResourceManager" in html
    assert "sample.txt" in html


def test_flask_api_diagnostics_endpoint(test_client):
    """Verifies that the JSON API endpoint returns real structured data."""
    response = test_client.get("/api/diagnostics")
    assert response.status_code == 200
    data = response.get_json()
    assert data["wsl"]["status"] == "Online"
    assert data["namenode_jmx"]["status"] == "Online"
    assert data["yarn_rm"]["status"] == "Online"


def test_flask_api_path_traversal_blocked(test_client):
    """Verifies that malicious path traversal queries receive HTTP 400."""
    response = test_client.get("/api/hdfs/list?path=../../etc/passwd")
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "Error"
    assert "Invalid path" in data["error"]
