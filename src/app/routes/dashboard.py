from flask import Blueprint, render_template, jsonify
import subprocess

# Blueprint definition
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

# HDFS overview API
@dashboard_bp.route('/', methods=['GET'])
def dashboard_view():
    """Render the main dashboard page."""
    return render_template('dashboard.html')


@dashboard_bp.route('/api/hdfs/overview', methods=['GET'])
def hdfs_overview():
    """Return basic HDFS storage metrics.
    Uses `hdfs dfsadmin -report` and parses total/used capacity.
    """
    cmd = [
        'wsl.exe', '-d', 'Ubuntu', '--',
        '/home/chethan/hadoop-3.5.0/bin/hdfs', 'dfsadmin', '-report'
    ]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=10)
        total = used = 0
        for line in out.splitlines():
            if 'Configured Capacity:' in line:
                total = int(line.split(':')[1].strip().split()[0])
            if 'DFS Used:' in line:
                used = int(line.split(':')[1].strip().split()[0])
        return jsonify({
            'total_bytes': total,
            'used_bytes': used,
            'free_bytes': max(total - used, 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Recent jobs API
from .mapreduce import _job_registry

@dashboard_bp.route('/api/jobs/recent', methods=['GET'])
def recent_jobs():
    """Return a list of recent MapReduce jobs from the in‑memory registry.
    The registry preserves insertion order, so we take the last 5 entries.
    """
    recent = []
    for job_id, info in list(_job_registry.items())[-5:]:
        recent.append({
            'job_id': job_id,
            'job_class': info.get('job_class'),
            'status': info.get('status'),
            'output_path': info.get('output_path')
        })
    return jsonify(recent)
