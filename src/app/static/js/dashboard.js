(() => {
  const $ = (id) => document.getElementById(id);
  let storageChart = null;
  const bytes = (value) => {
    if (!Number.isFinite(Number(value))) return 'Unavailable';
    const n = Number(value);
    if (n === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.min(Math.floor(Math.log(Math.abs(n)) / Math.log(1024)), units.length - 1);
    return `${(n / (1024 ** i)).toFixed(i > 1 ? 1 : 0)} ${units[i]}`;
  };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function getJson(url) {
    const response = await fetch(url, {headers: {'Accept':'application/json'}});
    const data = await response.json();
    if (!response.ok || data?.error) throw new Error(data?.error || `Request failed (${response.status})`);
    return data;
  }
  function renderChart(used, free) {
    if (!window.Chart || !$('hdfsStorageChart')) return;
    const canvas = $('hdfsStorageChart');
    if (storageChart) storageChart.destroy();
    storageChart = new Chart(canvas, {
      type: 'doughnut',
      data: { labels: ['Used', 'Free'], datasets: [{ data: [used, free], backgroundColor: ['#bd6b6d', '#e5ddd4'], borderWidth: 0, hoverOffset: 5 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '78%', plugins: { legend: {display:false}, tooltip: { callbacks: { label: ctx => `${ctx.label}: ${bytes(ctx.raw)}` } } } }
    });
  }
  async function loadStorage() {
    const info = $('hdfsStorageInfo');
    try {
      const data = await getJson('/dashboard/api/hdfs/overview');
      const total = Number(data.total_bytes), used = Number(data.used_bytes), free = Number(data.free_bytes);
      if (![total, used, free].every(Number.isFinite) || total <= 0) throw new Error('HDFS returned no usable capacity metrics. Check that the NameNode is running.');
      $('metricTotal').textContent = bytes(total);
      $('metricUsed').textContent = bytes(used);
      $('metricFree').textContent = bytes(free);
      $('metricUsedPct').textContent = `${Math.min(100, used / total * 100).toFixed(1)}% of configured capacity`;
      $('storagePercent').textContent = `${Math.min(100, used / total * 100).toFixed(0)}%`;
      $('legendUsed').textContent = bytes(used);
      $('legendFree').textContent = bytes(free);
      info.textContent = `Updated ${new Date().toLocaleTimeString()}`;
      renderChart(used, free);
    } catch (error) {
      ['metricTotal','metricUsed','metricFree','storagePercent'].forEach(id => $(id).textContent = '—');
      $('metricUsedPct').textContent = 'Metrics unavailable';
      $('legendUsed').textContent = 'Unavailable';
      $('legendFree').textContent = 'Unavailable';
      info.innerHTML = `<div class="inline-error"><i class="bi bi-exclamation-circle"></i><span>${escapeHtml(error.message)}</span></div>`;
      if (storageChart) { storageChart.destroy(); storageChart = null; }
      const notice = $('dashboardNotice');
      notice.textContent = 'HDFS storage metrics could not be loaded. Other dashboard sections may still be available.';
      notice.classList.remove('d-none');
    }
  }
  async function loadJobs() {
    const list = $('recentJobs');
    try {
      const jobs = await getJson('/dashboard/api/jobs/recent');
      $('metricJobs').textContent = Array.isArray(jobs) ? jobs.length : '—';
      if (!Array.isArray(jobs) || jobs.length === 0) {
        list.innerHTML = `<div class="empty-state"><i class="bi bi-inbox"></i><strong>No jobs submitted yet</strong><span>Start a job from the MapReduce Lab to see it here.</span><a class="text-link" href="/mapreduce/">Open MapReduce Lab <i class="bi bi-arrow-up-right"></i></a></div>`;
        return;
      }
      list.innerHTML = jobs.slice().reverse().map(job => `<div class="job-row"><div class="job-row-icon"><i class="bi bi-cpu"></i></div><div class="job-row-main"><strong>${escapeHtml(job.job_class || 'MapReduce job')}</strong><small>${escapeHtml(String(job.job_id || '').slice(0, 8))} · ${escapeHtml(job.output_path || 'Output path unavailable')}</small></div><span class="job-state state-${escapeHtml(String(job.status || 'unknown').toLowerCase())}">${escapeHtml(job.status || 'UNKNOWN')}</span></div>`).join('');
    } catch (error) {
      $('metricJobs').textContent = '—';
      list.innerHTML = `<div class="empty-state error-state"><i class="bi bi-exclamation-triangle"></i><strong>Could not load jobs</strong><span>${escapeHtml(error.message)}</span></div>`;
    }
  }
  async function refresh() {
    $('refreshDashboard').disabled = true;
    $('refreshDashboard').innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Refreshing';
    await Promise.allSettled([loadStorage(), loadJobs()]);
    $('refreshDashboard').disabled = false;
    $('refreshDashboard').innerHTML = '<i class="bi bi-arrow-clockwise me-2"></i>Refresh data';
  }
  document.addEventListener('DOMContentLoaded', () => {
    $('refreshDashboard')?.addEventListener('click', refresh);
    refresh();
  });
})();
