"""
HDFS File Manager Blueprint.
Exposes endpoints for interactive directory browsing, file uploads,
downloads, directory creation, copy, rename, and deletion with safety controls.
"""

import subprocess

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template,
    request,
    stream_with_context,
)

from ..services.hadoop_adapter import (
    HadoopAdapter,
    HadoopExecutionError,
    HadoopItemExistsError,
    HadoopNotFoundError,
    HadoopPathError,
    ProtectedPathError,
)
from ..services.hdfs_service import HdfsService

file_manager_bp = Blueprint("file_manager", __name__)


def get_hdfs_service() -> HdfsService:
    """Instantiates an HdfsService using the current app configuration."""
    config = current_app.config.get("HADOOP_CONFIG_INSTANCE")
    adapter = HadoopAdapter(config)
    return HdfsService(adapter=adapter, config=config)


@file_manager_bp.route("/file-manager")
@file_manager_bp.route("/files")
def file_manager_view():
    """Renders the primary HDFS File Manager interface."""
    path = request.args.get("path", "/user/chethan")
    service = get_hdfs_service()

    # Keep GET navigation read-only and fast; setup/job routes create workspace folders.

    try:
        data = service.browse_directory(path)
    except HadoopPathError as exc:
        # Fallback to root if user supplied an invalid path
        data = service.browse_directory("/")
        data["error"] = f"Requested path was invalid: {str(exc)}"
    except Exception as exc:
        data = {
            "status": "Error",
            "current_path": path,
            "parent_path": "/",
            "breadcrumbs": service.build_breadcrumbs(path if path.startswith("/") else "/"),
            "entries": [],
            "total_count": 0,
            "source": "None",
            "is_protected": False,
            "error": f"Failed to load directory: {str(exc)}"
        }

    return render_template("file_manager.html", data=data)


@file_manager_bp.route("/api/files/browse", methods=["GET"])
def api_browse_directory():
    """Returns directory listing and metadata as JSON."""
    path = request.args.get("path", "/user/chethan")
    service = get_hdfs_service()

    try:
        data = service.browse_directory(path)
        status_code = 200 if data["status"] == "Online" else (404 if "not found" in (data.get("error") or "").lower() else 500)
        return jsonify(data), status_code
    except HadoopPathError as exc:
        return jsonify({"status": "Error", "error": f"Invalid path: {str(exc)}"}), 400
    except Exception as exc:
        return jsonify({"status": "Error", "error": f"Failed to browse directory: {str(exc)}"}), 500


@file_manager_bp.route("/api/files/download", methods=["GET"])
def api_download_file():
    """Streams a file from HDFS as an HTTP attachment download."""
    path = request.args.get("path")
    if not path:
        return jsonify({"status": "Error", "error": "Query parameter 'path' is required."}), 400

    service = get_hdfs_service()
    try:
        stream, filename = service.get_download_stream(path)
        response = Response(stream_with_context(stream), mimetype="application/octet-stream")
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except HadoopPathError as exc:
        return jsonify({"status": "Error", "error": f"Invalid path: {str(exc)}"}), 400
    except HadoopNotFoundError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 404
    except HadoopExecutionError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"status": "Error", "error": f"Failed to download file: {str(exc)}"}), 500


@file_manager_bp.route("/api/files/mkdir", methods=["POST"])
def api_create_directory():
    """Creates a new folder in HDFS."""
    payload = request.get_json(silent=True) or {}
    parent_path = payload.get("parent_path") or request.form.get("parent_path")
    folder_name = payload.get("folder_name") or request.form.get("folder_name")

    if not parent_path or not folder_name:
        return jsonify({
            "status": "Error",
            "error": "Both 'parent_path' and 'folder_name' are required."
        }), 400

    service = get_hdfs_service()
    try:
        result = service.create_directory(parent_path, folder_name)
        return jsonify(result), 201
    except ProtectedPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 403
    except HadoopItemExistsError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 409
    except HadoopPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 400
    except HadoopExecutionError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"status": "Error", "error": f"Unexpected error: {str(exc)}"}), 500


@file_manager_bp.route("/api/files/upload", methods=["POST"])
def api_upload_file():
    """Uploads a file from client into HDFS."""
    if "file" not in request.files:
        return jsonify({"status": "Error", "error": "No file payload found in request."}), 400

    uploaded_file = request.files["file"]
    target_dir = request.form.get("target_dir", "/user/chethan")
    overwrite = request.form.get("overwrite", "false").lower() in ("true", "1", "yes")

    service = get_hdfs_service()
    try:
        result = service.handle_upload(uploaded_file, target_dir, overwrite=overwrite)
        return jsonify(result), 201
    except ProtectedPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 403
    except HadoopItemExistsError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 409
    except HadoopPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 400
    except HadoopExecutionError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"status": "Error", "error": f"Upload failed: {str(exc)}"}), 500


@file_manager_bp.route("/api/files/copy", methods=["POST"])
def api_copy_item():
    """Copies an item within HDFS."""
    payload = request.get_json(silent=True) or {}
    source_path = payload.get("source_path") or request.form.get("source_path")
    dest_dir = payload.get("dest_dir") or request.form.get("dest_dir")
    new_name = payload.get("new_name") or request.form.get("new_name")
    overwrite = bool(payload.get("overwrite", False))

    if not source_path or not dest_dir:
        return jsonify({"status": "Error", "error": "Both 'source_path' and 'dest_dir' are required."}), 400

    service = get_hdfs_service()
    try:
        result = service.copy_item(source_path, dest_dir, new_name=new_name, overwrite=overwrite)
        return jsonify(result), 200
    except ProtectedPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 403
    except HadoopNotFoundError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 404
    except HadoopItemExistsError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 409
    except HadoopPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 400
    except HadoopExecutionError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"status": "Error", "error": f"Copy failed: {str(exc)}"}), 500


@file_manager_bp.route("/api/files/rename", methods=["POST"])
def api_rename_item():
    """Renames an item within HDFS."""
    payload = request.get_json(silent=True) or {}
    source_path = payload.get("source_path") or request.form.get("source_path")
    new_name = payload.get("new_name") or request.form.get("new_name")

    if not source_path or not new_name:
        return jsonify({"status": "Error", "error": "Both 'source_path' and 'new_name' are required."}), 400

    service = get_hdfs_service()
    try:
        result = service.rename_item(source_path, new_name)
        return jsonify(result), 200
    except ProtectedPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 403
    except HadoopNotFoundError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 404
    except HadoopItemExistsError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 409
    except HadoopPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 400
    except HadoopExecutionError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"status": "Error", "error": f"Rename failed: {str(exc)}"}), 500


@file_manager_bp.route("/api/files/delete", methods=["POST"])
def api_delete_item():
    """Deletes a file or directory from HDFS with explicit confirmation for directories."""
    payload = request.get_json(silent=True) or {}
    path = payload.get("path") or request.form.get("path")
    recursive = bool(payload.get("recursive", False))
    confirmation_name = payload.get("confirmation_name") or request.form.get("confirmation_name")

    if not path:
        return jsonify({"status": "Error", "error": "Parameter 'path' is required."}), 400

    service = get_hdfs_service()
    try:
        result = service.delete_item(path, recursive=recursive, confirmation_name=confirmation_name)
        return jsonify(result), 200
    except ProtectedPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 403
    except HadoopNotFoundError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 404
    except HadoopPathError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 400
    except HadoopExecutionError as exc:
        return jsonify({"status": "Error", "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "Error", "error": f"Delete failed: {str(exc)}"}), 500
