(() => {
  const $ = id => document.getElementById(id);
  let activeJobId = null, pollingTimer = null, activeAlgorithm = 'WordCount', rawResult = '', samplePaths = {};
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    let data; try { data = await response.json(); } catch { throw new Error(`Unexpected response from server (${response.status})`); }
    if (!response.ok) throw new Error([data.error || `Request failed (${response.status})`, data.details].filter(Boolean).join(' — '));
    return data;
  }
  function feedback(message, type = 'info') { $('submitFeedback').innerHTML = `<div class="alert alert-${type} mb-0" role="alert">${escapeHtml(message)}</div>`; }
  function setStatus(status) { const el = $('jobStatus'); el.textContent = status || 'Unknown'; el.className = `status-pill status-${String(status || 'unknown').toLowerCase()}`; }
  function stopPolling() { if (pollingTimer) clearInterval(pollingTimer); pollingTimer = null; }
  const descriptions = {
    WordCount: { info: '<strong>Text input</strong><p>Counts whitespace-separated tokens. Punctuation and letter case follow the Java implementation; tokens are not silently normalized.</p><div class="format-example"><span>Example input</span><code>hadoop is useful</code><code>hadoop processes data</code></div>', path: '/user/chethan/sample.txt', output: 'wordcount' },
    MatrixMultiplication: { info: '<strong>Structured matrix input</strong><p>Each record describes one matrix element. The current matrix implementation uses one reducer to compute the complete product.</p><div class="format-example"><span>Record format</span><code>M row column value</code><code>N row column value</code></div>', path: '', output: 'matrix' },
    WeatherAnalysis: { info: '<strong>Weather CSV</strong><p>Expected columns: Year, Month, StationID, MaxTemp, MinTemp, Precipitation. Reports valid records and the mean of each record’s maximum/minimum temperature midpoint by station.</p><div class="format-example"><span>Output</span><code>Station · valid records · average temperature</code></div>', path: '', output: 'weather' }
  };
  function updateAlgorithmInfo() {
    activeAlgorithm = $('jobType').value; const item = descriptions[activeAlgorithm]; $('algorithmInfo').innerHTML = item.info;
    if (samplePaths[activeAlgorithm]) $('inputPath').value = samplePaths[activeAlgorithm];
    else if (item.path) $('inputPath').value = item.path;
    else $('inputPath').value = '';
    $('outputName').value = item.output;
    const reducerInput = $('reducers');
    const reducerHelp = reducerInput?.closest('.field')?.querySelector('.field-help');
    if (reducerInput) {
      const matrix = activeAlgorithm === 'MatrixMultiplication';
      reducerInput.disabled = matrix;
      reducerInput.value = matrix ? '1' : (reducerInput.value || '1');
      if (reducerHelp) reducerHelp.textContent = matrix ? 'Fixed at 1 for this implementation.' : 'Choose 1–8 reducer tasks.';
    }
  }
  function updateStage(status, log = '') {
    let stage = 'input', label = 'Preparing input';
    if (status === 'FINISHED') { stage = 'output'; label = 'Job finished — output available'; }
    else if (['FAILED', 'ERROR'].includes(status)) { stage = 'output'; label = `Job ${status.toLowerCase()} — inspect logs`; }
    else if (/reduce|reducing/i.test(log)) { stage = 'reduce'; label = 'Reduce stage indicated by Hadoop logs'; }
    else if (/shuffle|sort/i.test(log)) { stage = 'shuffle'; label = 'Shuffle/sort indicated by Hadoop logs'; }
    else if (/map|mapper/i.test(log)) { stage = 'map'; label = 'Map stage indicated by Hadoop logs'; }
    else if (status === 'RUNNING') { stage = 'map'; label = 'Hadoop job running; waiting for stage details'; }
    document.querySelectorAll('.workflow-step').forEach(el => { el.classList.toggle('stage-active', el.dataset.stage === stage); el.classList.toggle('stage-done', status === 'FINISHED'); });
    $('stageText').textContent = label;
  }
  function showJob(data) {
    activeJobId = data.job_id; $('jobEmptyState').classList.add('d-none'); $('jobDetails').classList.remove('d-none');
    $('jobId').textContent = data.job_id; $('outputPath').textContent = data.output_path || 'Assigned by server'; $('jobLog').textContent = 'Job submitted. Waiting for Hadoop output…';
    $('visualResult').classList.add('d-none'); $('jobResult').classList.add('d-none'); $('fetchResultBtn').classList.add('d-none');
    $('progressBar').style.width = '0%'; $('progressLabel').textContent = 'Waiting for application ID'; $('progressHint').textContent = 'Progress is reported by YARN when available.'; setStatus(data.status || 'RUNNING'); updateStage(data.status || 'RUNNING');
  }
  async function pollProgress() { if (!activeJobId) return; try { const p = await requestJson(`/mapreduce/progress/${encodeURIComponent(activeJobId)}`); if (Number.isFinite(Number(p.progress))) { const n = Math.max(0, Math.min(100, Number(p.progress))); $('progressBar').style.width = `${n}%`; $('progressLabel').textContent = `${n.toFixed(0)}%`; } else $('progressLabel').textContent = p.state || 'Progress unavailable'; $('progressHint').textContent = `YARN state: ${p.state || 'unknown'}${p.finalStatus ? ` · final status: ${p.finalStatus}` : ''}`; } catch (e) { $('progressLabel').textContent = 'Unavailable'; $('progressHint').textContent = `YARN progress unavailable: ${e.message}`; } }
  async function pollStatus() { if (!activeJobId) return; try { const d = await requestJson(`/mapreduce/status/${encodeURIComponent(activeJobId)}`); setStatus(d.status); $('jobLog').textContent = d.log || 'No log output received yet.'; $('jobLog').scrollTop = $('jobLog').scrollHeight; updateStage(d.status, d.log || ''); if (['FINISHED', 'FAILED', 'ERROR'].includes(d.status)) { stopPolling(); if (d.status === 'FINISHED') $('fetchResultBtn').classList.remove('d-none'); else feedback(`Job ${d.status.toLowerCase()}. Review the execution log for details.`, 'danger'); return; } if (d.app_id) await pollProgress(); } catch (e) { feedback(`Unable to refresh job status: ${e.message}`, 'danger'); } }
  function parseLines(raw) { return raw.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => { const m = line.match(/^(.*?)\s+(.*?)$/); return m ? { key: m[1].trim(), value: m[2].trim() } : null; }).filter(Boolean); }
  function renderTable(headers, rows, search = true) { const showSearch = search && rows.length > 10; const searchBox = showSearch ? '<input class="form-control result-search" id="resultSearch" type="search" placeholder="Filter results…" aria-label="Filter results">' : ''; if (!rows.length) { $('resultVisualization').innerHTML = '<p class="empty-result">No result rows were returned. Check the raw output and Hadoop execution log.</p>'; return; } const table = `<div class="table-responsive"><table class="table result-table"><thead><tr>${headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}</tr></thead><tbody id="resultRows">${rows.map(row => `<tr>${row.map(v => `<td>${escapeHtml(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`; $('resultVisualization').innerHTML = searchBox + `<div class="result-count">${rows.length.toLocaleString()} result row(s)</div>` + table; const input = $('resultSearch'); input?.addEventListener('input', () => { const q = input.value.toLowerCase(); $('resultRows').querySelectorAll('tr').forEach(tr => tr.hidden = !tr.textContent.toLowerCase().includes(q)); }); }
  function visualizeResult(raw) {
    rawResult = raw; $('visualResult').classList.remove('d-none'); $('jobResult').textContent = raw || '(The output file was empty.)'; $('resultVisualization').innerHTML = '';
    if (activeAlgorithm === 'WordCount') { const rows = parseLines(raw).map(x => [x.key, x.value]); $('resultHeading').textContent = 'Word frequency results'; $('resultSummary').textContent = 'Each row is a key and the count produced by the reducer.'; renderTable(['Token', 'Count'], rows); }
    else if (activeAlgorithm === 'MatrixMultiplication') { const cells = parseLines(raw).map(x => { const m = x.key.match(/(\d+)\s*[,\t:]\s*(\d+)/); return m ? { r: Number(m[1]), c: Number(m[2]), v: Number(x.value) } : null; }).filter(Boolean); $('resultHeading').textContent = 'Matrix product'; $('resultSummary').textContent = 'Values are placed into cells using the coordinates emitted by the reducer.'; if (cells.length) { const maxR = Math.max(...cells.map(x => x.r)), maxC = Math.max(...cells.map(x => x.c)); const rows = []; for (let r = 0; r <= maxR; r++) { const row = [r]; for (let c = 0; c <= maxC; c++) { const cell = cells.find(x => x.r === r && x.c === c); row.push(cell ? cell.v : '—'); } rows.push(row); } renderTable(['Row / Col', ...Array.from({ length: maxC + 1 }, (_, i) => `Col ${i}`)], rows, false); } else renderTable(['Coordinate', 'Value'], parseLines(raw).map(x => [x.key, x.value]), false); }
    else { $('resultHeading').textContent = 'Weather summary'; $('resultSummary').textContent = 'The key, valid observation count and average are shown as returned by the reducer.'; const rows = parseLines(raw).map(x => { const parts = x.value.split(/\s+/); return [x.key, parts[0] || '—', parts.slice(1).join(' ') || '—']; }); renderTable(['Group / station', 'Valid records', 'Average temperature'], rows); }
  }
  $('jobType')?.addEventListener('change', updateAlgorithmInfo);
  document.querySelectorAll('.path-chip').forEach(btn => btn.addEventListener('click', () => { const job = btn.dataset.job; if (job) { $('jobType').value = job; updateAlgorithmInfo(); if (!samplePaths[job] && job !== 'WordCount') feedback('Generate random samples first, or choose an existing file with Browse HDFS.', 'warning'); $('inputPath').focus(); } }));
  let browserCurrentPath = '/user/chethan/inputs';
  async function loadInputBrowser(path = '/user/chethan/inputs') {
    const panel = $('inputBrowser');
    const entries = $('browserEntries');
    panel.classList.remove('d-none');
    $('browserPath').textContent = path;
    $('browserMessage').textContent = 'Loading directory…';
    entries.innerHTML = '<p class="field-help">Loading HDFS entries…</p>';
    try {
      const data = await requestJson(`/mapreduce/browse-inputs?path=${encodeURIComponent(path)}`);
      browserCurrentPath = data.path || path;
      $('browserPath').textContent = browserCurrentPath;
      const rows = data.entries || [];
      if (!rows.length) entries.innerHTML = '<p class="field-help p-2">This directory is empty.</p>';
      else entries.innerHTML = rows.map(item => {
        const isDir = item.type === 'DIRECTORY';
        const icon = isDir ? 'folder' : 'file-earmark-text';
        const size = isDir ? 'Folder' : `${Number(item.length || 0).toLocaleString()} B`;
        return `<button type="button" class="input-browser-entry" data-path="${escapeHtml(item.path)}" data-action="${isDir ? 'open' : 'select'}" title="${isDir ? 'Open folder' : 'Use this input file'}"><span class="input-browser-name"><i class="bi bi-${icon}"></i>${escapeHtml(item.name)}</span><span class="input-browser-size">${size}</span></button>`;
      }).join('');
      $('browserMessage').textContent = `${rows.length} item(s) · ${data.source || 'HDFS'}`;
    } catch (error) {
      entries.innerHTML = `<p class="text-danger p-2">${escapeHtml(error.message)}</p>`;
      $('browserMessage').textContent = 'Could not load this directory.';
    }
  }
  $('browseInputBtn')?.addEventListener('click', () => loadInputBrowser('/user/chethan/inputs'));
  $('browserRefreshBtn')?.addEventListener('click', () => loadInputBrowser(browserCurrentPath));
  $('browserUpBtn')?.addEventListener('click', () => {
    if (browserCurrentPath === '/user/chethan/inputs') return;
    const parent = browserCurrentPath.slice(0, browserCurrentPath.lastIndexOf('/')) || '/user/chethan/inputs';
    loadInputBrowser(parent);
  });
  $('browserCloseBtn')?.addEventListener('click', () => $('inputBrowser').classList.add('d-none'));
  $('browserEntries')?.addEventListener('click', event => {
    const button = event.target.closest('button[data-path]');
    if (!button) return;
    const path = button.dataset.path;
    if (button.dataset.action === 'open') loadInputBrowser(path);
    else {
      $('inputPath').value = path;
      $('inputBrowser').classList.add('d-none');
      feedback(`Selected HDFS input: ${path}`, 'success');
    }
  });
  $('prepareSamplesBtn')?.addEventListener('click', async event => { const btn = event.currentTarget; btn.disabled = true; const old = btn.innerHTML; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Generating…'; feedback('Generating fresh randomized datasets and uploading them to HDFS…'); try { const data = await requestJson('/mapreduce/prepare-samples', { method: 'POST', headers: { 'Accept': 'application/json' } }); samplePaths = data.paths || {}; updateAlgorithmInfo(); feedback(`${data.message} Choose an algorithm, then use its Quick select button or Browse HDFS. New files are under ${data.directory}.`, 'success'); } catch (e) { feedback(`${e.message}${e.details ? `: ${e.details}` : ''}`, 'danger'); } finally { btn.disabled = false; btn.innerHTML = old; } });
  $('jobForm')?.addEventListener('submit', async event => { event.preventDefault(); stopPolling(); const form = event.currentTarget; if (!form.reportValidity()) return; const btn = $('submitJobBtn'); btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting…'; feedback('Validating input and submitting to Hadoop…'); try { const payload = Object.fromEntries(new FormData(form).entries()); payload.reducers = Number(payload.reducers); const data = await requestJson('/mapreduce/submit', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }, body: JSON.stringify(payload) }); showJob(data); feedback('Job submitted. Waiting for actual Hadoop status…', 'success'); await pollStatus(); if (activeJobId && $('jobStatus').textContent !== 'FINISHED') pollingTimer = setInterval(pollStatus, 3000); } catch (e) { feedback(e.message, 'danger'); } finally { btn.disabled = false; btn.innerHTML = '<i class="bi bi-play-fill me-2"></i>Run job'; } });

  $('fetchResultBtn')?.addEventListener('click', async () => {
    if (!activeJobId) return;

    const btn = $('fetchResultBtn');
    btn.disabled = true;

    try {
      const d = await requestJson(
        `/mapreduce/result/${encodeURIComponent(activeJobId)}`
      );

      $('inputPathDisplay').textContent = d.input_path || 'Unavailable';
      $('resultPathDisplay').textContent = d.output_path || 'Unavailable';

      $('inputPreview').textContent = d.input_preview || (
        d.input_preview_error
          ? 'Input preview unavailable. See the note below.'
          : '(Input file is empty.)'
      );

      $('inputPreviewNote').textContent = d.input_preview_error
        ? `Preview unavailable: ${d.input_preview_error}`
        : d.input_truncated
          ? 'Preview limited to 12,000 characters. The original HDFS file is unchanged.'
          : 'Showing the input content read from HDFS.';

      visualizeResult(d.result || '');

      feedback('Input and output loaded from HDFS.', 'success');
    } catch (e) {
      feedback(`Could not fetch job results: ${e.message}`, 'danger');
    } finally {
      btn.disabled = false;
    }
  });

  $('toggleRaw')?.addEventListener('click', () => { const pre = $('jobResult'); const show = pre.classList.contains('d-none'); pre.classList.toggle('d-none', !show); $('toggleRaw').textContent = show ? 'Hide raw output' : 'Show raw output'; });
  $('copyJobId')?.addEventListener('click', async () => { if (activeJobId) try { await navigator.clipboard.writeText(activeJobId); feedback('Job ID copied.', 'success'); } catch { feedback(`Job ID: ${activeJobId}`); } });
  $('copyOutputPath')?.addEventListener('click', async () => { const path = $('outputPath').textContent; try { await navigator.clipboard.writeText(path); feedback('Output path copied.', 'success'); } catch { feedback(path); } });
  updateAlgorithmInfo();
})();
