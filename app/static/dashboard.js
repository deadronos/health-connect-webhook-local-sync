const form = document.getElementById('filters-form');
const fromDateInput = document.getElementById('from-date');
const toDateInput = document.getElementById('to-date');
const recordTypeSelect = document.getElementById('record-type');
const overviewCards = document.getElementById('overview-cards');
const highlightsCards = document.getElementById('highlights-cards');
const activityCards = document.getElementById('activity-cards');
const chart = document.getElementById('timeseries-chart');
const timeseriesSummary = document.getElementById('timeseries-summary');
const featureTitle = document.getElementById('feature-title');
const featureTags = document.getElementById('feature-tags');
const heroFeaturedRecord = document.getElementById('hero-featured-record');
const heroTotalEvents = document.getElementById('hero-total-events');
const heroRecordTypeCount = document.getElementById('hero-record-type-count');
const heroLastCapture = document.getElementById('hero-last-capture');
const selectedLatest = document.getElementById('selected-latest');
const selectedAverage = document.getElementById('selected-average');
const selectedRange = document.getElementById('selected-range');
const selectedCount = document.getElementById('selected-count');
const eventsBody = document.getElementById('events-body');
const exportLink = document.getElementById('export-link');
const railLinks = Array.from(document.querySelectorAll('.rail-link'));
const dashboardSections = Array.from(document.querySelectorAll('.dashboard-section'));

const integerFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const decimalFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const CUMULATIVE_RECORDS = new Set(['steps', 'distance', 'active_calories', 'total_calories', 'exercise', 'nutrition']);
const AVERAGE_RECORDS = new Set(['heart_rate', 'resting_heart_rate', 'heart_rate_variability', 'oxygen_saturation', 'vo2_max', 'basal_metabolic_rate']);
const LATEST_RECORDS = new Set(['weight', 'height', 'body_fat', 'lean_body_mass']);
const dashboardState = {
  activeSectionId: 'hero',
  overviewCards: [],
  lastEvents: [],
  unitMap: new Map(),
};

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

function prettifyRecordType(recordType) {
  return String(recordType || '')
    .split('_')
    .filter(Boolean)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(' ');
}

function formatNumber(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return '—';
  }
  if (Number.isInteger(numericValue) || Math.abs(numericValue) >= 100) {
    return integerFormatter.format(numericValue);
  }
  return decimalFormatter.format(numericValue);
}

function formatMetric(value, unit) {
  if (value === null || value === undefined) {
    return '—';
  }
  const formatted = formatNumber(value);
  if (!unit || unit === 'count') {
    return formatted;
  }
  return `${formatted} ${unit}`;
}

function formatShortDateTime(timestampMs) {
  if (!timestampMs) {
    return '—';
  }
  return new Date(timestampMs).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatShortDate(timestampMs) {
  if (!timestampMs) {
    return '—';
  }
  return new Date(timestampMs).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

function recordTone(recordType) {
  const normalised = String(recordType || '');
  if (normalised.includes('heart')) {
    return 'tone-blush';
  }
  if (normalised.includes('calories') || normalised.includes('nutrition')) {
    return 'tone-sky';
  }
  if (normalised.includes('water') || normalised.includes('steps') || normalised.includes('distance')) {
    return 'tone-peach';
  }
  if (normalised.includes('weight') || normalised.includes('body') || normalised.includes('height')) {
    return 'tone-violet';
  }
  return 'tone-cream';
}

function recordBadge(recordType) {
  return prettifyRecordType(recordType)
    .split(' ')
    .map((word) => word[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

function featureConfig(recordType) {
  if (LATEST_RECORDS.has(recordType)) {
    return { stat: 'latest_value', label: 'Latest snapshot' };
  }
  if (AVERAGE_RECORDS.has(recordType)) {
    return { stat: 'avg', label: 'Average reading' };
  }
  if (CUMULATIVE_RECORDS.has(recordType)) {
    return { stat: 'sum', label: 'Window total' };
  }
  return { stat: 'sum', label: 'Window total' };
}

function chooseCardValue(card, stat) {
  if (!card) {
    return null;
  }
  switch (stat) {
    case 'avg':
      return card.avg ?? card.latest_value ?? card.sum ?? card.max ?? card.min;
    case 'latest_value':
      return card.latest_value ?? card.avg ?? card.max ?? card.min ?? card.sum;
    case 'count':
      return card.count;
    case 'sum':
    default:
      return card.sum ?? card.latest_value ?? card.avg ?? card.max ?? card.min;
  }
}

function sortCards(cards) {
  return [...cards].sort((left, right) => {
    return (right.count - left.count)
      || ((right.latest_at ?? 0) - (left.latest_at ?? 0))
      || ((right.sum ?? 0) - (left.sum ?? 0));
  });
}

function prioritiseCards(cards, featuredCard) {
  const sorted = sortCards(cards);
  if (!featuredCard) {
    return sorted;
  }
  return [
    featuredCard,
    ...sorted.filter((card) => card.record_type !== featuredCard.record_type),
  ];
}

function pickFeaturedCard(cards) {
  if (!cards.length) {
    return null;
  }
  if (recordTypeSelect.value) {
    return cards.find((card) => card.record_type === recordTypeSelect.value) ?? null;
  }
  return sortCards(cards)[0] ?? null;
}

function buildUnitMap(events) {
  return events.reduce((map, event) => {
    if (!map.has(event.record_type) && event.unit) {
      map.set(event.record_type, event.unit);
    }
    return map;
  }, new Map());
}

function rangeText(card, unit) {
  if (card.min === null || card.min === undefined || card.max === null || card.max === undefined) {
    return '—';
  }
  return `${formatMetric(card.min, unit)} → ${formatMetric(card.max, unit)}`;
}

function populateRecordTypeOptions(cards) {
  const currentSelection = recordTypeSelect.value;
  if (!cards.length) {
    recordTypeSelect.innerHTML = '<option value="">No record types available</option>';
    return;
  }

  recordTypeSelect.innerHTML = [
    '<option value="">Auto-select from data</option>',
    ...sortCards(cards).map((card) => `<option value="${escapeHtml(card.record_type)}">${escapeHtml(prettifyRecordType(card.record_type))}</option>`),
  ].join('');

  if (cards.some((card) => card.record_type === currentSelection)) {
    recordTypeSelect.value = currentSelection;
  }
}

function sectionElement(sectionId) {
  return document.getElementById(sectionId);
}

function setActiveSection(sectionId) {
  if (!sectionId) {
    return;
  }

  dashboardState.activeSectionId = sectionId;

  railLinks.forEach((link) => {
    const isActive = link.dataset.sectionTarget === sectionId;
    link.classList.toggle('is-active', isActive);
    if (isActive) {
      link.setAttribute('aria-current', 'location');
    } else {
      link.removeAttribute('aria-current');
    }
  });

  dashboardSections.forEach((section) => {
    section.classList.toggle('is-section-active', section.id === sectionId);
  });

  document.querySelectorAll('button[data-section-target]:not([data-record-type])').forEach((button) => {
    const isActive = button.dataset.sectionTarget === sectionId;
    button.classList.toggle('is-active', isActive);
    button.setAttribute('aria-pressed', String(isActive));
  });
}

function focusSection(sectionId, { behavior = 'smooth', updateHash = true, focusTarget = true } = {}) {
  const section = sectionElement(sectionId);
  if (!section) {
    return;
  }

  setActiveSection(sectionId);
  section.scrollIntoView({ behavior, block: 'start' });

  if (focusTarget) {
    window.requestAnimationFrame(() => {
      section.focus({ preventScroll: true });
    });
  }

  if (updateHash) {
    window.history.replaceState(null, '', `#${sectionId}`);
  }
}

function activateMetric(recordType, sectionId = 'feature') {
  if (!recordType) {
    focusSection(sectionId);
    return;
  }

  const needsRefresh = recordTypeSelect.value !== recordType;
  recordTypeSelect.value = recordType;

  if (needsRefresh) {
    refreshDashboard({ reuseOverview: true, focusSectionId: sectionId });
    return;
  }

  focusSection(sectionId);
}

function initialiseSectionObserver() {
  if (!('IntersectionObserver' in window)) {
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    const visibleEntries = entries
      .filter((entry) => entry.isIntersecting)
      .sort((left, right) => right.intersectionRatio - left.intersectionRatio);

    if (visibleEntries[0]?.target?.id) {
      setActiveSection(visibleEntries[0].target.id);
    }
  }, {
    rootMargin: '-25% 0px -45% 0px',
    threshold: [0.2, 0.4, 0.65],
  });

  dashboardSections.forEach((section) => observer.observe(section));
}

function renderHeroSummary(cards, featuredCard) {
  const latestCapture = cards.reduce((latest, card) => Math.max(latest, card.latest_at ?? 0), 0);
  const totalEvents = cards.reduce((sum, card) => sum + card.count, 0);

  heroFeaturedRecord.textContent = featuredCard
    ? prettifyRecordType(featuredCard.record_type)
    : 'No metric selected';
  heroTotalEvents.textContent = cards.length ? integerFormatter.format(totalEvents) : '—';
  heroRecordTypeCount.textContent = cards.length ? integerFormatter.format(cards.length) : '—';
  heroLastCapture.textContent = latestCapture ? formatShortDateTime(latestCapture) : '—';
}

function renderFeatureDetails(card, unit) {
  if (!card) {
    featureTitle.textContent = 'Trend spotlight';
    selectedLatest.textContent = '—';
    selectedAverage.textContent = '—';
    selectedRange.textContent = '—';
    selectedCount.textContent = '—';
    return;
  }

  featureTitle.textContent = prettifyRecordType(card.record_type);
  selectedLatest.textContent = formatMetric(card.latest_value ?? card.avg ?? card.sum, unit);
  selectedAverage.textContent = formatMetric(card.avg, unit);
  selectedRange.textContent = rangeText(card, unit);
  selectedCount.textContent = integerFormatter.format(card.count);
}

function renderFeatureTags(cards, featuredCard) {
  if (!cards.length) {
    featureTags.innerHTML = '<span class="feature-chip">Waiting for overview…</span>';
    return;
  }

  featureTags.innerHTML = sortCards(cards)
    .slice(0, 6)
    .map((card) => {
      const isActive = featuredCard && card.record_type === featuredCard.record_type;
      return `
        <button
          type="button"
          class="feature-chip-button${isActive ? ' is-active' : ''}"
          data-record-type="${escapeHtml(card.record_type)}"
          data-section-target="feature"
          aria-pressed="${isActive}"
        >
          ${escapeHtml(prettifyRecordType(card.record_type))}
        </button>
      `;
    })
    .join('');
}

function renderOverview(cards, unitMap, featuredCard) {
  const rankedCards = prioritiseCards(cards, featuredCard).slice(0, 3);

  if (!rankedCards.length) {
    overviewCards.innerHTML = '<div class="empty-state">No overview data for the selected range.</div>';
    return;
  }

  overviewCards.innerHTML = rankedCards.map((card) => {
    const unit = unitMap.get(card.record_type);
    const isActive = featuredCard && featuredCard.record_type === card.record_type;
    return `
      <button
        type="button"
        class="stat-card stat-card-button card-button ${recordTone(card.record_type)}${isActive ? ' is-active' : ''}"
        data-record-type="${escapeHtml(card.record_type)}"
        data-section-target="overview"
        aria-pressed="${isActive}"
      >
        <h3>${escapeHtml(prettifyRecordType(card.record_type))}</h3>
        <div class="stat-row"><span>Latest</span><strong>${escapeHtml(formatMetric(card.latest_value ?? card.avg ?? card.sum, unit))}</strong></div>
        <div class="stat-row"><span>Average</span><strong>${escapeHtml(formatMetric(card.avg, unit))}</strong></div>
        <div class="stat-row"><span>Range</span><strong>${escapeHtml(rangeText(card, unit))}</strong></div>
        <div class="stat-row"><span>Records</span><strong>${integerFormatter.format(card.count)}</strong></div>
      </button>
    `;
  }).join('');
}

function renderActivityCards(cards, unitMap, featuredCard) {
  const rankedCards = sortCards(cards).slice(0, 4);

  if (!rankedCards.length) {
    activityCards.innerHTML = '<div class="empty-state">No quick-glance cards yet.</div>';
    return;
  }

  activityCards.innerHTML = rankedCards.map((card) => {
    const unit = unitMap.get(card.record_type);
    const config = featureConfig(card.record_type);
    const primaryValue = chooseCardValue(card, config.stat);
    const isActive = featuredCard && featuredCard.record_type === card.record_type;

    return `
      <button
        type="button"
        class="activity-card activity-card-button card-button${isActive ? ' is-active' : ''}"
        data-record-type="${escapeHtml(card.record_type)}"
        data-section-target="feature"
        aria-pressed="${isActive}"
      >
        <div>
          <span class="activity-card-label">${escapeHtml(prettifyRecordType(card.record_type))}</span>
          <strong class="activity-card-value">${escapeHtml(formatMetric(primaryValue, unit))}</strong>
        </div>
        <div class="activity-card-meta">${escapeHtml(config.label)} · ${integerFormatter.format(card.count)} records</div>
        <div class="activity-card-note">Updated ${escapeHtml(formatShortDateTime(card.latest_at))}</div>
      </button>
    `;
  }).join('');
}

function renderHighlights(cards, events, featuredCard, unitMap) {
  const totalEvents = cards.reduce((sum, card) => sum + card.count, 0);
  const latestCapture = events.reduce((latest, event) => Math.max(latest, event.captured_at ?? 0), 0);
  const mostActive = sortCards(cards)[0] ?? null;
  const featuredConfig = featuredCard ? featureConfig(featuredCard.record_type) : { label: 'Window total', stat: 'sum' };
  const featuredUnit = featuredCard ? unitMap.get(featuredCard.record_type) : null;
  const featuredValue = featuredCard ? chooseCardValue(featuredCard, featuredConfig.stat) : null;

  const summaryCards = [
    {
      title: featuredCard ? featuredConfig.label : 'Selected metric',
      value: featuredCard ? formatMetric(featuredValue, featuredUnit) : '—',
      meta: featuredCard ? `Jump to ${prettifyRecordType(featuredCard.record_type)} trend` : 'Pick a metric to spotlight',
      badge: featuredCard ? recordBadge(featuredCard.record_type) : '—',
      recordType: featuredCard?.record_type,
      sectionTarget: 'feature',
      isActive: dashboardState.activeSectionId === 'feature',
    },
    {
      title: 'Window events',
      value: totalEvents ? integerFormatter.format(totalEvents) : '—',
      meta: 'Open the recent event stream',
      badge: 'EV',
      sectionTarget: 'events',
      isActive: dashboardState.activeSectionId === 'events',
    },
    {
      title: 'Tracked metrics',
      value: cards.length ? integerFormatter.format(cards.length) : '—',
      meta: mostActive ? `Top signal: ${prettifyRecordType(mostActive.record_type)}` : 'Waiting for data',
      badge: 'OV',
      sectionTarget: 'overview',
      isActive: dashboardState.activeSectionId === 'overview',
    },
    {
      title: 'Latest capture',
      value: latestCapture ? formatShortDate(latestCapture) : '—',
      meta: mostActive ? `Top signal: ${prettifyRecordType(mostActive.record_type)}` : 'Waiting for data',
      badge: 'HS',
      sectionTarget: 'hero',
      isActive: dashboardState.activeSectionId === 'hero',
    },
  ];

  highlightsCards.innerHTML = summaryCards.map((card) => `
    <button
      type="button"
      class="highlight-card highlight-card-button card-button${card.isActive ? ' is-active' : ''}"
      ${card.recordType ? `data-record-type="${escapeHtml(card.recordType)}"` : ''}
      data-section-target="${escapeHtml(card.sectionTarget)}"
      aria-pressed="${card.isActive}"
    >
      <div class="highlight-card-header">
        <div>
          <p class="highlight-card-title">${escapeHtml(card.title)}</p>
          <p class="highlight-card-value">${escapeHtml(card.value)}</p>
        </div>
        <div class="highlight-card-badge">${escapeHtml(card.badge)}</div>
      </div>
      <div class="highlight-card-meta">${escapeHtml(card.meta)}</div>
    </button>
  `).join('');
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
    highlightsCards.innerHTML = `<div class="empty-state">${message}</div>`;
  }
}

function renderChart(points, recordType, config, unit) {
  if (!points.length) {
    chart.innerHTML = '<text class="chart-empty" x="50%" y="50%" dominant-baseline="middle" text-anchor="middle">No time-series data yet</text>';
    timeseriesSummary.textContent = recordType
      ? `${prettifyRecordType(recordType)} · no points available for this range`
      : 'No points available for the selected filters.';
    return;
  }

  const width = 800;
  const height = 320;
  const paddingX = 42;
  const paddingTop = 28;
  const paddingBottom = 48;
  const values = points.map((point) => Number(point.value || 0));
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const valueRange = maxValue - minValue || 1;
  const chartWidth = width - paddingX * 2;
  const chartHeight = height - paddingTop - paddingBottom;
  const step = chartWidth / Math.max(points.length - 1, 1);
  const baselineY = height - paddingBottom;

  const coordinates = points.map((point, index) => {
    const x = paddingX + (step * index);
    const ratio = (Number(point.value || 0) - minValue) / valueRange;
    const y = baselineY - (ratio * chartHeight);
    return {
      x,
      y,
      label: formatShortDate(point.bucket_start),
      value: Number(point.value || 0),
    };
  });

  const linePath = coordinates.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
  const areaPath = `${linePath} L ${coordinates[coordinates.length - 1].x} ${baselineY} L ${coordinates[0].x} ${baselineY} Z`;
  const lastPoint = coordinates[coordinates.length - 1];
  const labelStep = Math.max(1, Math.ceil(coordinates.length / 6));
  const gridLines = [0, 1, 2, 3].map((index) => {
    const y = paddingTop + ((chartHeight / 3) * index);
    return `<line class="chart-grid-line" x1="${paddingX}" y1="${y}" x2="${width - paddingX}" y2="${y}"></line>`;
  }).join('');
  const xLabels = coordinates.map((point, index) => {
    if (index % labelStep !== 0 && index !== coordinates.length - 1) {
      return '';
    }
    return `<text class="chart-label" x="${point.x}" y="${height - 18}" text-anchor="middle">${escapeHtml(point.label)}</text>`;
  }).join('');
  const pointDots = coordinates.map((point) => `
    <circle class="chart-dot" cx="${point.x}" cy="${point.y}" r="5"></circle>
  `).join('');
  const total = values.reduce((sum, value) => sum + value, 0);
  const statSummary = config.stat === 'sum'
    ? formatMetric(total, unit)
    : formatMetric(chooseCardValue({ avg: values.reduce((sum, value) => sum + value, 0) / values.length, latest_value: lastPoint.value }, config.stat), unit);

  chart.innerHTML = `
    <defs>
      <linearGradient id="chartAreaGradient" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="rgba(247, 212, 178, 0.55)"></stop>
        <stop offset="100%" stop-color="rgba(247, 212, 178, 0)"></stop>
      </linearGradient>
    </defs>
    ${gridLines}
    <path class="chart-area" d="${areaPath}"></path>
    <path class="chart-line" d="${linePath}"></path>
    ${pointDots}
    <text class="chart-value-label" x="${lastPoint.x}" y="${Math.max(lastPoint.y - 16, 18)}" text-anchor="middle">${escapeHtml(formatMetric(lastPoint.value, unit))}</text>
    ${xLabels}
  `;

  timeseriesSummary.textContent = `${prettifyRecordType(recordType)} · ${config.label.toLowerCase()} ${statSummary} · ${points.length} points`;
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
        <td>${escapeHtml(prettifyRecordType(event.record_type))}</td>
        <td>${escapeHtml(formatMetric(event.value, event.unit))}</td>
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

function setLoadingState({ preserveOverview = false } = {}) {
  if (!preserveOverview) {
    overviewCards.innerHTML = '<div class="empty-state">Refreshing overview…</div>';
    highlightsCards.innerHTML = '<div class="empty-state">Refreshing highlight cards…</div>';
    activityCards.innerHTML = '<div class="empty-state">Refreshing quick-glance cards…</div>';
    featureTags.innerHTML = '<span class="feature-chip">Refreshing signals…</span>';
    featureTitle.textContent = 'Trend spotlight';
    heroFeaturedRecord.textContent = 'Refreshing metric…';
    heroTotalEvents.textContent = '—';
    heroRecordTypeCount.textContent = '—';
    heroLastCapture.textContent = '—';
  }

  selectedLatest.textContent = '—';
  selectedAverage.textContent = '—';
  selectedRange.textContent = '—';
  selectedCount.textContent = '—';
  timeseriesSummary.textContent = 'Refreshing selected signal…';
  chart.innerHTML = '<text class="chart-empty" x="50%" y="50%" dominant-baseline="middle" text-anchor="middle">Refreshing chart…</text>';
  eventsBody.innerHTML = '<tr><td class="empty-state" colspan="5">Refreshing events…</td></tr>';
}

async function refreshDashboard({ reuseOverview = false, focusSectionId = null } = {}) {
  try {
    const shouldReuseOverview = reuseOverview && dashboardState.overviewCards.length > 0;
    setLoadingState({ preserveOverview: shouldReuseOverview });

    let cards = dashboardState.overviewCards;
    if (!shouldReuseOverview) {
      const overview = await fetchJson('/analytics/overview', buildParams());
      cards = Array.isArray(overview.cards) ? overview.cards : [];
      dashboardState.overviewCards = cards;
      populateRecordTypeOptions(cards);
    }

    const featuredCard = pickFeaturedCard(cards);
    renderHeroSummary(cards, featuredCard);
    renderFeatureTags(cards, featuredCard);
    renderFeatureDetails(featuredCard, featuredCard ? dashboardState.unitMap.get(featuredCard.record_type) : null);
    renderActivityCards(cards, dashboardState.unitMap, featuredCard);
    renderOverview(cards, dashboardState.unitMap, featuredCard);
    updateExportLink();

    const eventParams = buildParams({ includeRecordType: true, limit: 25 });
    const featureRecordType = featuredCard?.record_type || '';
    const config = featureRecordType ? featureConfig(featureRecordType) : { stat: 'sum', label: 'Window total' };
    const timeseriesParams = buildParams({ includeRecordType: true });

    if (featureRecordType) {
      timeseriesParams.set('record_type', featureRecordType);
      timeseriesParams.set('bucket', 'day');
      timeseriesParams.set('stat', config.stat);
    }

    const [timeseriesResponse, eventsResponse] = await Promise.all([
      featureRecordType
        ? fetchJson('/analytics/timeseries', timeseriesParams)
        : Promise.resolve({ points: [] }),
      fetchJson('/analytics/events', eventParams),
    ]);

    const events = Array.isArray(eventsResponse.events) ? eventsResponse.events : [];
    const unitMap = buildUnitMap(events);
    dashboardState.lastEvents = events;
    dashboardState.unitMap = unitMap;

    renderFeatureDetails(featuredCard, featureRecordType ? unitMap.get(featureRecordType) : null);
    renderActivityCards(cards, unitMap, featuredCard);
    renderOverview(cards, unitMap, featuredCard);
    renderHighlights(cards, events, featuredCard, unitMap);
    renderChart(timeseriesResponse.points || [], featureRecordType, config, featureRecordType ? unitMap.get(featureRecordType) : null);
    renderEvents(events);
    updateExportLink();

    if (focusSectionId) {
      focusSection(focusSectionId);
    }
  } catch (error) {
    const message = escapeHtml(error.message || 'Dashboard request failed');
    overviewCards.innerHTML = `<div class="empty-state">${message}</div>`;
    highlightsCards.innerHTML = `<div class="empty-state">${message}</div>`;
    activityCards.innerHTML = `<div class="empty-state">${message}</div>`;
    featureTags.innerHTML = `<span class="feature-chip">${message}</span>`;
    chart.innerHTML = `<text class="chart-empty" x="50%" y="50%" dominant-baseline="middle" text-anchor="middle">${message}</text>`;
    eventsBody.innerHTML = `<tr><td class="empty-state" colspan="5">${message}</td></tr>`;
  }
}

function handleDashboardClick(event) {
  const metricControl = event.target.closest('[data-record-type]');
  if (metricControl) {
    event.preventDefault();
    activateMetric(metricControl.dataset.recordType, metricControl.dataset.sectionTarget || 'feature');
    return;
  }

  const sectionControl = event.target.closest('[data-section-target]');
  if (!sectionControl) {
    return;
  }

  event.preventDefault();
  focusSection(sectionControl.dataset.sectionTarget);
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  refreshDashboard();
});

recordTypeSelect.addEventListener('change', () => {
  refreshDashboard();
});

exportLink.addEventListener('click', downloadExport);
document.addEventListener('click', handleDashboardClick);

document.addEventListener('DOMContentLoaded', () => {
  initialiseDates();
  initialiseSectionObserver();
  const hashSectionId = window.location.hash ? window.location.hash.slice(1) : '';
  if (hashSectionId && sectionElement(hashSectionId)) {
    setActiveSection(hashSectionId);
  } else {
    setActiveSection('hero');
  }
  refreshDashboard();
});
