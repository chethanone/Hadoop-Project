import socket
import pytest

def _hadoop_available():
    try:
        s = socket.create_connection(("localhost", 9000), timeout=1)
        s.close()
        return True
    except OSError:
        return False

def pytest_collection_modifyitems(config, items):
    if not _hadoop_available():
        skip_marker = pytest.mark.skip(reason="Hadoop cluster not reachable")
        for item in items:
            # Skip any test defined in live test files
            try:
                if item.fspath.basename in ("test_live_integration.py", "test_hdfs_mutations_live.py"):
                    item.add_marker(skip_marker)
            except Exception:
                pass
