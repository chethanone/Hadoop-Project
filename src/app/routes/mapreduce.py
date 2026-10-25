import os
import random
import subprocess
import threading
import uuid
from pathlib import Path
from datetime import datetime

import requests
from flask import Blueprint, current_app, jsonify, render_template, request

mapreduce_bp = Blueprint('mapreduce', __name__, url_prefix='/mapreduce')
_job_registry = {}


def _extract_app_id(line):
    """Extract a YARN application ID from a Hadoop log line, if present."""
    if "application_" in line:
        for part in line.strip().split():
            if part.startswith("application_"):
                return part
    return None


def _is_safe_hdfs_path(path: str, must_exist: bool = False) -> bool:
    """Validate an HDFS path and optionally check that it exists."""
    if not path or not path.startswith('/'):
        return False
    if '..' in path or '\\' in path:
        return False

    if must_exist:
        test_cmd = [
            'wsl.exe', '-d', 'Ubuntu', '--',
            '/home/chethan/hadoop-3.5.0/bin/hdfs', 'dfs', '-test', '-e', path
        ]
        try:
            subprocess.check_call(
                test_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except (subprocess.CalledProcessError, OSError):
            return False
    return True


def _run_job_async(job_id, job_class, input_path, output_path, reducers):
    """Run a Hadoop job asynchronously and retain a bounded execution log."""
    try:
        jar_path = '/mnt/c/hadoop_proj/jars/mapreduce-jobs.jar'

        # Create only the standard workspace directories if missing.
        # Existing HDFS data is not deleted or overwritten.
        subprocess.run(
            [
                'wsl.exe', '-d', 'Ubuntu', '--',
                '/home/chethan/hadoop-3.5.0/bin/hdfs', 'dfs', '-mkdir', '-p',
                '/user/chethan/inputs', '/user/chethan/outputs'
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=True
        )

        # The Java jobs in this project accept exactly two positional
        # arguments: input HDFS path and output HDFS path. Passing reducers
        # as an extra positional argument causes the Java Usage error.
        # Reducer-count wiring must be implemented in the Java jobs/config,
        # not by appending a third positional argument here.
        hadoop_cmd = [
            'wsl.exe', '-d', 'Ubuntu', '--',
            '/home/chethan/hadoop-3.5.0/bin/yarn',
            'jar', jar_path,
            job_class, input_path, output_path
        ]

        proc = subprocess.Popen(
            hadoop_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        _job_registry[job_id]['process'] = proc
        log = _job_registry[job_id]['log']

        if proc.stdout is not None:
            for line in proc.stdout:
                log.append(line)
                if len(log) > 500:
                    del log[0]
                app_id = _extract_app_id(line)
                if app_id:
                    _job_registry[job_id]['app_id'] = app_id

        proc.wait()
        _job_registry[job_id]['status'] = (
            'FINISHED' if proc.returncode == 0 else 'FAILED'
        )
    except Exception as exc:
        _job_registry[job_id]['status'] = 'ERROR'
        _job_registry[job_id]['log'].append(f'{type(exc).__name__}: {exc}\n')


@mapreduce_bp.route('/', methods=['GET'])
def index():
    return render_template('mapreduce.html')


@mapreduce_bp.route('/prepare-samples', methods=['POST'])
def prepare_sample_inputs():
    """Generate fresh, valid sample datasets and upload them to a unique HDFS folder."""
    config = current_app.config.get('HADOOP_CONFIG_INSTANCE')
    hdfs_bin = getattr(config, 'HDFS_BIN_WSL', '/home/chethan/hadoop-3.5.0/bin/hdfs')
    windows_root = Path(getattr(config, 'WIN_WORKSPACE', str(Path(current_app.root_path).parents[1])))
    runtime_dir = windows_root / '.runtime_samples'
    runtime_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = uuid.uuid4().hex[:8]
    base_dir = f'/user/chethan/inputs/demo_{stamp}_{suffix}'
    generated = {}

    # Fresh word-count data: vocabulary and ordering change on each request.
    vocabulary = ['hadoop', 'mapreduce', 'records', 'cluster', 'data', 'worker', 'reducer', 'mapper', 'storage', 'analysis', 'fast', 'reliable']
    word_lines = [' '.join(random.choices(vocabulary, k=random.randint(5, 10))) for _ in range(5)]
    generated['WordCount'] = ('sample_wordcount.txt', '\n'.join(word_lines) + '\n')

    # Fresh 2x2 matrices with small integer values, valid for MatrixMultiplication.
    matrix_lines = []
    for label in ('M', 'N'):
        for row in range(2):
            for col in range(2):
                matrix_lines.append(f'{label} {row} {col} {random.randint(1, 9)}')
    generated['MatrixMultiplication'] = ('sample_matrix.txt', '\n'.join(matrix_lines) + '\n')

    # Matches the WeatherAnalysis implementation: Year,Month,StationID,MaxTemp,MinTemp,Precipitation.
    weather_lines = ['Year,Month,StationID,MaxTemp,MinTemp,Precipitation']
    for station in ('S1', 'S2', 'S3'):
        for month in range(1, 5):
            minimum = random.randint(8, 24)
            maximum = minimum + random.randint(5, 16)
            precipitation = round(random.uniform(0, 12), 1)
            weather_lines.append(f'2025,{month},{station},{maximum},{minimum},{precipitation}')
    generated['WeatherAnalysis'] = ('sample_weather.csv', '\n'.join(weather_lines) + '\n')

    local_files = []
    try:
        for _job, (filename, content) in generated.items():
            local_path = runtime_dir / f'{Path(filename).stem}_{suffix}{Path(filename).suffix}'
            local_path.write_text(content, encoding='utf-8', newline='')
            local_files.append(local_path)

        subprocess.run(
            ['wsl.exe', '-d', 'Ubuntu', '--', hdfs_bin, 'dfs', '-mkdir', '-p', base_dir],
            capture_output=True, text=True, timeout=20, check=True
        )

        paths = {}
        for job_name, (filename, _content) in generated.items():
            local_path = next(item for item in local_files if item.name.startswith(Path(filename).stem + '_'))
            # Translate the generated Windows path to the configured WSL-mounted project path.
            relative = local_path.relative_to(windows_root).as_posix()
            source_wsl = f"{getattr(config, 'WSL_WORKSPACE', '/mnt/c/hadoop_proj').rstrip('/')}/{relative}"
            target = f'{base_dir}/{filename}'
            subprocess.run(
                ['wsl.exe', '-d', 'Ubuntu', '--', hdfs_bin, 'dfs', '-put', source_wsl, target],
                capture_output=True, text=True, timeout=30, check=True
            )
            paths[job_name] = target

        return jsonify({
            'status': 'ok',
            'message': 'Fresh randomized sample datasets were generated and uploaded.',
            'paths': paths,
            'directory': base_dir,
            'sample_version': suffix
        }), 200
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return jsonify({
            'error': 'HDFS rejected the sample-input setup.',
            'details': detail[-2000:] or 'The WSL/Hadoop command failed without an error message.'
        }), 500
    except subprocess.TimeoutExpired as exc:
        return jsonify({
            'error': 'Sample-input setup timed out.',
            'details': f'Command exceeded its timeout ({exc.timeout}s). Check that WSL and HDFS are running.'
        }), 504
    except Exception as exc:
        current_app.logger.exception('Preparing randomized Hadoop sample inputs failed')
        return jsonify({'error': 'Could not prepare sample inputs in HDFS.', 'details': str(exc)}), 500
    finally:
        for local_path in local_files:
            try:
                local_path.unlink(missing_ok=True)
            except OSError:
                current_app.logger.warning('Could not remove temporary sample file: %s', local_path)


@mapreduce_bp.route('/browse-inputs', methods=['GET'])
def browse_inputs():
    """Fast, one-directory-at-a-time input picker backed by WebHDFS with CLI fallback."""
    path = request.args.get('path', '/user/chethan/inputs').strip()
    root = '/user/chethan/inputs'
    if (not path.startswith(root) or path != root and not path.startswith(root + '/')
            or '..' in path or '\\' in path):
        return jsonify({'error': 'Browse is limited to /user/chethan/inputs.'}), 400

    config = current_app.config.get('HADOOP_CONFIG_INSTANCE')
    try:
        # WebHDFS LISTSTATUS is usually faster than launching a new WSL process per navigation.
        url = f"{getattr(config, 'NAMENODE_HTTP_URL', 'http://localhost:9870')}/webhdfs/v1{path}?op=LISTSTATUS"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            statuses = response.json().get('FileStatuses', {}).get('FileStatus', [])
            entries = []
            for item in statuses:
                name = item.get('pathSuffix', '')
                item_path = path.rstrip('/') + '/' + name
                entries.append({'name': name, 'path': item_path, 'type': item.get('type'), 'length': item.get('length', 0)})
            entries.sort(key=lambda item: (item['type'] != 'DIRECTORY', item['name'].lower()))
            return jsonify({'path': path, 'entries': entries, 'source': 'WebHDFS'})
        if response.status_code == 404:
            return jsonify({'error': 'HDFS directory not found.', 'path': path}), 404
    except requests.RequestException:
        pass

    hdfs_bin = getattr(config, 'HDFS_BIN_WSL', '/home/chethan/hadoop-3.5.0/bin/hdfs')
    try:
        result = subprocess.run(
            ['wsl.exe', '-d', 'Ubuntu', '--', hdfs_bin, 'dfs', '-ls', path],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5
        )
        if result.returncode:
            return jsonify({'error': (result.stderr or 'Unable to list HDFS directory.').strip(), 'path': path}), 502
        entries = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 8 and not line.startswith('Found'):
                item_path = parts[-1]
                entries.append({'name': os.path.basename(item_path), 'path': item_path,
                                'type': 'DIRECTORY' if parts[0].startswith('d') else 'FILE',
                                'length': int(parts[4]) if parts[4].isdigit() else 0})
        entries.sort(key=lambda item: (item['type'] != 'DIRECTORY', item['name'].lower()))
        return jsonify({'path': path, 'entries': entries, 'source': 'HDFS CLI'})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'HDFS listing timed out. Check that HDFS is running.'}), 504

@mapreduce_bp.route('/submit', methods=['POST'])
def submit_job():
    data = request.get_json(silent=True) or request.form
    job_name = data.get('job')
    input_path = data.get('input')
    output_base = data.get('output') or 'output'

    if not isinstance(input_path, str) or not isinstance(output_base, str):
        return jsonify({'error': 'Input path and output name must be text values'}), 400

    job_map = {
        'WordCount': 'WordCount',
        'MatrixMultiplication': 'MatrixMultiplication',
        'WeatherAnalysis': 'WeatherAnalysis',
    }
    job_class = job_map.get(job_name)
    if not job_class:
        return jsonify({'error': 'Unsupported job name'}), 400

    # Matrix multiplication requires one reducer to assemble each complete output cell.
    if job_class == 'MatrixMultiplication':
        reducers = 1
    else:
        try:
            reducers = int(data.get('reducers', 1))
        except (TypeError, ValueError):
            return jsonify({'error': 'Reducers must be an integer between 1 and 8'}), 400
        if not 1 <= reducers <= 8:
            return jsonify({'error': 'Reducers must be between 1 and 8'}), 400

    if not _is_safe_hdfs_path(input_path, must_exist=True):
        return jsonify({'error': 'Invalid or non-existent input path'}), 400

    if '/' in output_base or '..' in output_base or '\\' in output_base:
        return jsonify({'error': 'Invalid output name'}), 400

    allowed_prefix = '/user/chethan/outputs/'
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    output_path = (
        f'{allowed_prefix}{job_class.lower()}_{output_base}_'
        f'{timestamp}_{uuid.uuid4().hex[:6]}'
    )

    job_id = str(uuid.uuid4())
    _job_registry[job_id] = {
        'status': 'RUNNING',
        'log': [],
        'process': None,
        'output_path': output_path,
        'job_class': job_class,
        'input_path': input_path,
        'reducers': reducers,
        'app_id': None,
    }

    threading.Thread(
        target=_run_job_async,
        args=(job_id, job_class, input_path, output_path, reducers),
        daemon=True
    ).start()

    return jsonify({
        'job_id': job_id,
        'status': 'RUNNING',
        'output_path': output_path
    })


@mapreduce_bp.route('/status/<job_id>', methods=['GET'])
def job_status(job_id):
    info = _job_registry.get(job_id)
    if not info:
        return jsonify({'error': 'Job ID not found'}), 404

    return jsonify({
        'status': info['status'],
        'log': ''.join(info['log'][-200:]),
        'app_id': info.get('app_id'),
    })


@mapreduce_bp.route('/progress/<job_id>', methods=['GET'])
def job_progress(job_id):
    """Poll the YARN REST API when the job has a YARN application ID."""
    info = _job_registry.get(job_id)
    if not info:
        return jsonify({'error': 'Job ID not found'}), 404

    app_id = info.get('app_id')
    if not app_id:
        return jsonify({'error': 'Application ID not yet available'}), 202

    url = f'http://localhost:8088/ws/v1/cluster/apps/{app_id}'
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return jsonify({'error': 'Failed to query YARN'}), 502

        payload = resp.json()
        app = payload.get('app', {})
        return jsonify({
            'state': app.get('state'),
            'finalStatus': app.get('finalStatus'),
            'progress': app.get('progress'),
        })
    except Exception as exc:
        return jsonify({'error': 'YARN query error', 'details': str(exc)}), 500


@mapreduce_bp.route('/result/<job_id>', methods=['GET'])
def job_result(job_id):
    info = _job_registry.get(job_id)
    if not info:
        return jsonify({'error': 'Job ID not found'}), 404
    if info.get('status') != 'FINISHED':
        return jsonify({'error': 'Job not finished'}), 400

    hdfs = '/home/chethan/hadoop-3.5.0/bin/hdfs'
    input_path = info.get('input_path', '')
    output_path = info.get('output_path', '')

    try:
        # Prefer streamed WebHDFS preview with a byte limit; this avoids loading the full input into memory.
        from ..services.hadoop_adapter import HadoopAdapter
        adapter = HadoopAdapter(current_app.config.get('HADOOP_CONFIG_INSTANCE'))
        preview_limit = 12000
        preview_data = adapter.preview_hdfs_file(input_path, max_bytes=preview_limit, max_lines=300)
        input_preview = preview_data.get('content', '') if preview_data.get('status') == 'Online' else ''
        input_truncated = bool(preview_data.get('truncated', False))
        input_preview_error = preview_data.get('error') if preview_data.get('status') != 'Online' else None

        list_cmd = [
            'wsl.exe', '-d', 'Ubuntu', '--',
            hdfs, 'dfs', '-ls', output_path
        ]
        listing = subprocess.run(
            list_cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=15
        )
        if listing.returncode != 0:
            return jsonify({
                'error': 'Could not list the HDFS output directory.',
                'details': listing.stderr[-1500:]
            }), 500

        part_files = []
        for line in listing.stdout.splitlines():
            tokens = line.split()
            if len(tokens) >= 8:
                filename = tokens[-1]
                if os.path.basename(filename).startswith('part-'):
                    part_files.append(filename)

        if not part_files:
            return jsonify({
                'error': 'No reducer output files were found.',
                'input_path': input_path,
                'output_path': output_path
            }), 500

        cat_cmd = [
            'wsl.exe', '-d', 'Ubuntu', '--', hdfs, 'dfs', '-cat', *part_files
        ]
        output = subprocess.run(
            cat_cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )
        if output.returncode != 0:
            return jsonify({
                'error': 'Failed to read reducer output.',
                'details': output.stderr[-1500:]
            }), 500

        return jsonify({
            'result': output.stdout,
            'input_preview': input_preview,
            'input_truncated': input_truncated,
            'input_preview_error': input_preview_error,
            'input_path': input_path,
            'output_path': output_path,
            'job_class': info.get('job_class'),
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            'error': 'Timed out while reading HDFS input or output.'
        }), 504
    except Exception as exc:
        current_app.logger.exception('Could not retrieve MapReduce results')
        return jsonify({
            'error': 'Unexpected error while retrieving results.',
            'details': str(exc)
        }), 500
