"""
Diagnostics and Health Blueprint.
Exposes real-time health checks, cluster metrics, and read-only HDFS verification.
"""

from flask import Blueprint, current_app, jsonify, render_template, request

from ..services.hadoop_adapter import HadoopAdapter, HadoopPathError, HadoopRedirectError

diagnostics_bp = Blueprint("diagnostics", __name__)


def get_adapter() -> HadoopAdapter:
    """Helper to instantiate or retrieve HadoopAdapter from current app context."""
    return HadoopAdapter(current_app.config.get("HADOOP_CONFIG_INSTANCE"))


@diagnostics_bp.route("/")
def index():
    """Root route redirects to the main dashboard."""
    from flask import redirect, url_for
    return redirect(url_for('dashboard.dashboard_view'))


@diagnostics_bp.route("/diagnostics")
def diagnostics_page():
    """Renders the comprehensive environment diagnostics dashboard."""
    adapter = get_adapter()
    diag_data = adapter.run_full_diagnostics()
    return render_template("diagnostics.html", diag=diag_data)


@diagnostics_bp.route("/api/diagnostics", methods=["GET"])
def api_diagnostics():
    """Returns raw diagnostic telemetry as JSON."""
    adapter = get_adapter()
    diag_data = adapter.run_full_diagnostics()
    return jsonify(diag_data)


@diagnostics_bp.route("/api/hdfs/list", methods=["GET"])
def api_hdfs_list():
    """
    Read-only directory listing endpoint.
    Query param: path (default: /user/chethan)
    """
    path = request.args.get("path", "/user/chethan")
    adapter = get_adapter()

    try:
        result = adapter.list_hdfs_directory(path)
        status_code = 200 if result["status"] == "Online" else (404 if "not found" in (result.get("error") or "").lower() else 500)
        return jsonify(result), status_code
    except HadoopPathError as exc:
        return jsonify({
            "status": "Error",
            "path": path,
            "entries": [],
            "error": f"Invalid path: {str(exc)}"
        }), 400
    except Exception as exc:
        return jsonify({
            "status": "Error",
            "path": path,
            "entries": [],
            "error": f"Unexpected error: {str(exc)}"
        }), 500


@diagnostics_bp.route("/api/hdfs/preview", methods=["GET"])
def api_hdfs_preview():
    """
    Read-only text file preview endpoint.
    Query param: path (required)
    """
    path = request.args.get("path")
    if not path:
        return jsonify({"status": "Error", "error": "Query parameter 'path' is required."}), 400

    adapter = get_adapter()
    try:
        result = adapter.preview_hdfs_file(path)
        status_code = 200 if result["status"] == "Online" else 500
        return jsonify(result), status_code
    except HadoopPathError as exc:
        return jsonify({"status": "Error", "path": path, "error": f"Invalid path: {str(exc)}"}), 400
    except HadoopRedirectError as exc:
        return jsonify({"status": "Error", "path": path, "error": f"Security restriction: {str(exc)}"}), 403
    except Exception as exc:
        return jsonify({"status": "Error", "path": path, "error": f"Unexpected preview error: {str(exc)}"}), 500
