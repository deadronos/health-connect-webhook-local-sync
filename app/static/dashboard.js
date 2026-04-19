const form = document.getElementById('filters-form');
const fromDateInput = document.getElementById('from-date');
const toDateInput = document.getElementById('to-date');
const recordTypeSelect = document.getElementById('record-type');
const overviewCards = document.getElementById('overview-cards');
const chart = document.getElementById('timeseries-chart');
const timeseriesSummary = document.getElementById('timeseries-summary');
const eventsBody = document.getElementById('events-body');
const exportLink = document.getElementById('export-link');

const formatDate = (date) => date.toISOString().slice(0, 10);
const startOfDayMs = (value) => new Date(`${value}T00:00:00Z`).getTime();
const endOfDayMs = (value) => new Date(`${value}T23:59:59.999Z`).getTime();
const escapeHtml = (value) => String(value)
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

function redirectToLogin() {
  const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
  window.location.assign(`/login?next=${next}`);
}

function initialiseDates() {
  const today = new Date();
  const start = new Date(today);
  start.setUTCDate(today.getUTCDate() - 6);
  fromDateInput.value = formatDate(start);
  toDateInput.value = formatDate(today);
}

function buildParams({ includeRecordType = false, limit } = {}) {
  const params = new URLSearchParams();
  if (fromDateInput.value) {
    params.set('from_ms', String(startOfDayMs(fromDateInput.value)));
  }
  if (toDateInput.value) {
    params.set('to_ms', String(endOfDayMs(toDateInput.value)));
  }
  if (includeRecordType && recordTypeSelect.value) {
    params.set('record_type', recordTypeSelect.value);
  }
  if (typeof limit === 'number') {
    params.set('limit', String(limit));
  }
  return params;
}

async function fetchJson(path, params) {
  const url = params && params.toString() ? `${path}?${params.toString()}` : path;
  const response = await fetch(url, { credentials: 'same-origin' });
  if (response.status === 401) {
    redirectToLogin();
    throw new Error('Your dashboard session expired. Redirecting to login…');
  }
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return response.json();
}

function renderOverview(cards) {
  if (!cards.length) {
    overviewCards.innerHTML = '<div class="empty-state">No overview data for the selected range.</div>';
    recordTypeSelect.innerHTML = '<option value="">No record types available</option>';
    return;
  }

  overviewCards.innerHTML = cards.map((card) => `
    <article class="stat-card">
      <h3>${escapeHtml(card.record_type)}</h3>
      <div class="stat-row"><span>Count</span><strong>${card.count}</strong></div>
      <div class="stat-row"><span>Sum</span><strong>${card.sum ?? '—'}</strong></div>
      <div class="stat-row"><span>Average</span><strong>${card.avg ?? '—'}</strong></div>
      <div class="stat-row"><span>Range</span><strong>${card.min ?? '—'} → ${card.max ?? '—'}</strong></div>
    </article>
  `).join('');

  const currentSelection = recordTypeSelect.value;
  recordTypeSelect.innerHTML = [
    '<option value="">Auto-select from data</option>',
    ...cards.map((card) => `<option value="${escapeHtml(card.record_type)}">${escapeHtml(card.record_type)}</option>`),
  ].join('');

  if (cards.some((card) => card.record_type === currentSelection)) {
    recordTypeSelect.value = currentSelection;
  } else if (!recordTypeSelect.value && cards[0]) {
    recordTypeSelect.value = cards[0].record_type;
  }
}

async function downloadExport(event) {
  event.preventDefault();

  try {
    const response = await fetch(exportLink.href, { credentials: 'same-origin' });
    if (response.status === 401) {
      redirectToLogin();
      throw new Error('Your dashboard session expired. Redirecting to login…');
    }
    if (!response.ok) {
      throw new Error(`Export failed (${response.status})`);
    }

    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = 'health-events.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(downloadUrl);
  } catch (error) {
    const message = escapeHtml(error.message || 'CSV export failed');
    overviewCards.innerHTML = `<div class="empty-state">${message}</div>`;
  }
}

function renderChart(points, recordType) {
  if (!points.length) {
    chart.innerHTML = '<text class="chart-empty" x="50%" y="50%" dominant-baseline="middle" text-anchor="middle">No time-series data yet</text>';
    timeseriesSummary.textContent = 'No points available for the selected filters.';
    return;
  }

  const width = 800;
  const height = 240;
  const padding = 30;
  const maxValue = Math.max(...points.map((point) => point.value), 1);
  const barWidth = Math.max((width - padding * 2) / points.length - 10, 12);

  chart.innerHTML = points.map((point, index) => {
    const barHeight = ((height - padding * 2) * point.value) / maxValue;
    const x = padding + index * ((width - padding * 2) / points.length) + 5;
    const y = height - padding - barHeight;
    const label = new Date(point.bucket_start).toISOString().slice(0, 10);
    return `
      <rect class="chart-bar" x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="8" />
      <text class="chart-label" x="${x + barWidth / 2}" y="${height - 8}" text-anchor="middle">${label}</text>
    `;
  }).join('');

  const total = points.reduce((sum, point) => sum + point.value, 0);
  timeseriesSummary.textContent = `${recordType || 'Selected record'} · ${points.length} points · total ${total.toFixed(2)}`;
}

function renderEvents(events) {
  if (!events.length) {
    eventsBody.innerHTML = '<tr><td class="empty-state" colspan="5">No events found for the selected filters.</td></tr>';
    return;
  }

  eventsBody.innerHTML = events.map((event) => {
    const metadataText = event.metadata && Object.keys(event.metadata).length
      ? escapeHtml(JSON.stringify(event.metadata))
      : '—';
    const capturedAt = new Date(event.captured_at).toLocaleString();
    return `
      <tr>
        <td>${escapeHtml(event.record_type)}</td>
        <td>${event.value} ${escapeHtml(event.unit)}</td>
        <td>${escapeHtml(event.device_id || '—')}</td>
        <td>${escapeHtml(capturedAt)}</td>
        <td><span class="metadata-pill">${metadataText}</span></td>
      </tr>
    `;
  }).join('');
}

function updateExportLink() {
  exportLink.href = `/analytics/export.csv?${buildParams({ includeRecordType: true, limit: 1000 }).toString()}`;
}

async function refreshDashboard() {
  try {
    overviewCards.innerHTML = '<div class="empty-state">Refreshing overview…</div>';
    eventsBody.innerHTML = '<tr><td class="empty-state" colspan="5">Refreshing events…</td></tr>';

    const overview = await fetchJson('/analytics/overview', buildParams());
    renderOverview(overview.cards);

    const selectedRecordType = recordTypeSelect.value || overview.cards[0]?.record_type || '';
    updateExportLink();

    if (selectedRecordType) {
      const timeseriesParams = buildParams({ includeRecordType: true });
      timeseriesParams.set('record_type', selectedRecordType);
      timeseriesParams.set('bucket', 'day');
      timeseriesParams.set('stat', 'sum');
      const timeseries = await fetchJson('/analytics/timeseries', timeseriesParams);
      renderChart(timeseries.points, selectedRecordType);
    } else {
      renderChart([], '');
    }

    const eventParams = buildParams({ includeRecordType: true, limit: 25 });
    const events = await fetchJson('/analytics/events', eventParams);
    renderEvents(events.events);
    updateExportLink();
  } catch (error) {
    const message = escapeHtml(error.message || 'Dashboard request failed');
    overviewCards.innerHTML = `<div class="empty-state">${message}</div>`;
    chart.innerHTML = `<text class="chart-empty" x="50%" y="50%" dominant-baseline="middle" text-anchor="middle">${message}</text>`;
    eventsBody.innerHTML = `<tr><td class="empty-state" colspan="5">${message}</td></tr>`;
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  refreshDashboard();
});

recordTypeSelect.addEventListener('change', () => {
  refreshDashboard();
});

exportLink.addEventListener('click', downloadExport);

document.addEventListener('DOMContentLoaded', () => {
  initialiseDates();
  refreshDashboard();
});
