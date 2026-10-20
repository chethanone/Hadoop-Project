"""
Live Integration Tests for HDFS Mutating Operations (Phase 3).
Executes strictly within an isolated sandbox directory: /user/chethan/phase3_test_sandbox/
Guarantees complete immutability of existing files (/user/chethan/sample.txt and wordcount_output/).
"""
import io
import pytest
from src.app import create_app
from src.app.services.hadoop_adapter import HadoopAdapter, ProtectedPathError, HadoopItemExistsError
from src.app.services.hdfs_service import HdfsService

SANDBOX_DIR = "/user/chethan/phase3_test_sandbox"


@pytest.fixture(scope="module")
def live_adapter():
    return HadoopAdapter()


@pytest.fixture(scope="module")
def live_service(live_adapter):
    return HdfsService(adapter=live_adapter)


@pytest.fixture(scope="module")
def test_client():
    app = create_app("testing")
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="module", autouse=True)
def manage_sandbox(live_adapter):
    """
    Creates sandbox before tests and ensures clean teardown after all tests complete.
    Never alters or touches files outside the sandbox.
    """
    # Setup: ensure sandbox directory exists
    if live_adapter.exists(SANDBOX_DIR):
        live_adapter.delete_item(SANDBOX_DIR, recursive=True, confirmation_name="phase3_test_sandbox")
    live_adapter.mkdir(SANDBOX_DIR)

    yield

    # Teardown: cleanly delete sandbox directory and its contents
    if live_adapter.exists(SANDBOX_DIR):
        live_adapter.delete_item(SANDBOX_DIR, recursive=True, confirmation_name="phase3_test_sandbox")


def test_live_mkdir_in_sandbox(live_service, live_adapter):
    """Verifies creating a directory in the test sandbox."""
    res = live_service.create_directory(SANDBOX_DIR, "test_folder_alpha")
    assert res["status"] == "success"

    expected_path = f"{SANDBOX_DIR}/test_folder_alpha"
    assert live_adapter.exists(expected_path)
    assert live_adapter.is_directory(expected_path)


def test_live_upload_and_preview_file(live_service, live_adapter):
    """Verifies uploading a file into the sandbox and reading its preview."""
    file_bytes = b"Hello Apache Hadoop 3.5.0\nPhase 3 Live Mutation Test\n"
    file_obj = io.BytesIO(file_bytes)
    file_obj.filename = "test_upload_file.txt"

    res = live_service.handle_upload(file_obj, SANDBOX_DIR, overwrite=False)
    assert res["status"] == "success"
    assert res["filename"] == "test_upload_file.txt"
    assert res["bytes"] == len(file_bytes)

    target_path = f"{SANDBOX_DIR}/test_upload_file.txt"
    assert live_adapter.exists(target_path)
    assert not live_adapter.is_directory(target_path)

    # Preview and verify content fidelity
    preview = live_adapter.preview_hdfs_file(target_path)
    assert preview["status"] == "Online"
    assert "Hello Apache Hadoop 3.5.0" in preview["content"]
    assert "Phase 3 Live Mutation Test" in preview["content"]
    assert preview["bytes_read"] == len(file_bytes)


def test_live_copy_and_rename_file(live_service, live_adapter):
    """Verifies copying and renaming files inside the sandbox."""
    src = f"{SANDBOX_DIR}/test_upload_file.txt"
    copy_dest = f"{SANDBOX_DIR}/test_upload_copy.txt"
    renamed_dest = f"{SANDBOX_DIR}/test_upload_renamed.txt"

    # Copy
    copy_res = live_service.copy_item(src, SANDBOX_DIR, new_name="test_upload_copy.txt")
    assert copy_res["status"] == "success"
    assert live_adapter.exists(copy_dest)
    assert live_adapter.exists(src)  # Original still exists

    # Rename
    rename_res = live_service.rename_item(copy_dest, "test_upload_renamed.txt")
    assert rename_res["status"] == "success"
    assert live_adapter.exists(renamed_dest)
    assert not live_adapter.exists(copy_dest)  # Old name gone


def test_live_delete_file_single(live_service, live_adapter):
    """Verifies deleting a single file without recursive confirmation."""
    target = f"{SANDBOX_DIR}/test_upload_renamed.txt"
    assert live_adapter.exists(target)

    del_res = live_service.delete_item(target, recursive=False)
    assert del_res["status"] == "success"
    assert not live_adapter.exists(target)


def test_live_delete_directory_confirmation_enforcement(live_service, live_adapter):
    """
    Verifies that recursive directory deletion requires an exact
    confirmation matching the folder name.
    """
    folder_path = f"{SANDBOX_DIR}/confirm_folder"
    live_adapter.mkdir(folder_path)

    # Put a file inside to make it non-empty
    subfile = io.BytesIO(b"subfile content")
    subfile.filename = "child.txt"
    live_service.handle_upload(subfile, folder_path)

    # Attempt recursive delete with wrong confirmation name -> must raise
    with pytest.raises(Exception, match="Confirmation name mismatch"):
        live_adapter.delete_item(folder_path, recursive=True, confirmation_name="wrong_name")

    # Directory still exists
    assert live_adapter.exists(folder_path)

    # Supplying correct confirmation name -> succeeds
    del_res = live_adapter.delete_item(folder_path, recursive=True, confirmation_name="confirm_folder")
    assert del_res["status"] == "success"
    assert not live_adapter.exists(folder_path)


def test_live_protection_guard_sample_txt(live_service, live_adapter):
    """
    Guarantees that /user/chethan/sample.txt is completely protected
    against deletion, rename, and overwrite.
    """
    target = "/user/chethan/sample.txt"
    assert live_adapter.exists(target)

    # Attempt deletion
    with pytest.raises(ProtectedPathError, match="Cannot delete protected system path"):
        live_service.delete_item(target)

    # Attempt rename
    with pytest.raises(ProtectedPathError, match="Cannot rename protected system path"):
        live_service.rename_item(target, "sample_renamed.txt")

    # Attempt overwrite upload
    fake_file = io.BytesIO(b"malicious overwrite")
    fake_file.filename = "sample.txt"
    with pytest.raises(ProtectedPathError, match="Cannot overwrite protected system path"):
        live_service.handle_upload(fake_file, "/user/chethan", overwrite=True)

    # Target must remain intact
    assert live_adapter.exists(target)


def test_live_protection_guard_system_directories(live_service):
    """
    Guarantees that system paths (/user, /tmp, /, /user/chethan/wordcount_output)
    are strictly rejected when deletion is attempted.
    """
    protected_targets = [
        "/",
        "/tmp",
        "/user",
        "/user/chethan",
        "/user/chethan/wordcount_output",
        "/user/chethan/wordcount_output/_SUCCESS",
        "/user/chethan/wordcount_output/part-r-00000"
    ]
    for path in protected_targets:
        with pytest.raises(ProtectedPathError):
            live_service.delete_item(path, recursive=True, confirmation_name=path.split("/")[-1])


def test_live_file_manager_routes_end_to_end(test_client):
    """Verifies Flask file manager endpoints over HTTP."""
    # 1. View /file-manager HTML page
    resp = test_client.get("/file-manager?path=/user/chethan")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "HDFS File Explorer" in html
    assert "sample.txt" in html
    assert "wordcount_output" in html

    # 2. Browse API
    api_resp = test_client.get("/api/files/browse?path=/user/chethan")
    assert api_resp.status_code == 200
    browse_data = api_resp.get_json()
    assert browse_data["status"] == "Online"
    names = [e["name"] for e in browse_data["entries"]]
    assert "sample.txt" in names

    # 3. Download API on sample.txt
    dl_resp = test_client.get("/api/files/download?path=/user/chethan/sample.txt")
    assert dl_resp.status_code == 200
    assert dl_resp.headers["Content-Disposition"] == 'attachment; filename="sample.txt"'
    assert b"hadoop is powerful" in dl_resp.data

    # 4. Attempt API delete on protected path -> 403 Forbidden
    del_resp = test_client.post("/api/files/delete", json={
        "path": "/user/chethan/sample.txt"
    })
    assert del_resp.status_code == 403
    assert "Cannot delete protected system path" in del_resp.get_json()["error"]


def test_live_baseline_fidelity_post_mutation(live_adapter):
    """
    Final verification ensuring that all preexisting data
    remains 100% unaltered after all mutation tests.
    """
    # sample.txt verification
    sample_preview = live_adapter.preview_hdfs_file("/user/chethan/sample.txt")
    assert sample_preview["status"] == "Online"
    assert sample_preview["bytes_read"] == 58
    assert "hadoop is powerful" in sample_preview["content"]

    # wordcount_output verification
    wc_preview = live_adapter.preview_hdfs_file("/user/chethan/wordcount_output/part-r-00000")
    assert wc_preview["status"] == "Online"
    assert wc_preview["bytes_read"] == 46
    assert "hadoop\t2" in wc_preview["content"]
