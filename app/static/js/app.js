const form = document.getElementById('simulate-form');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');
const submitBtn = document.getElementById('submit-btn');
const loadingOverlay = document.getElementById('loading_overlay');
const loadingBar = document.getElementById('loading_bar');
const loadingPct = document.getElementById('loading_pct');
const loadingStage = document.getElementById('loading_stage');
const historyListEl = document.getElementById('history_list');
const refreshHistoryBtn = document.getElementById('refresh_history_btn');
const copyShareBtn = document.getElementById('copy_share_btn');
const exportPngBtn = document.getElementById('export_png_btn');

const el = {
  regret: document.getElementById('regret_score'),
  summary: document.getElementById('summary_line'),
  contextSignal: document.getElementById('context_signal'),
  sourceLine: document.getElementById('source_line'),
  timelineCards: document.getElementById('timeline_cards'),
  incomeSummary: document.getElementById('income_summary'),
  lifestyleSummary: document.getElementById('lifestyle_summary'),
  incomeProjection: document.getElementById('income_projection'),
  lifestyleProjection: document.getElementById('lifestyle_projection'),
  assumptions: document.getElementById('assumptions'),
  snapshots: document.getElementById('snapshot_list'),
  sources: document.getElementById('sources_list'),
};

let loadingTimer = null;
let stageTimer = null;
let activeShareUrl = window.location.pathname || '/';

function clearChildren(node) {
  while (node && node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function pushList(node, text) {
  const li = document.createElement('li');
  li.textContent = text;
  node.appendChild(li);
}

function pct(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function toAbsoluteUrl(path) {
  try {
    return new URL(path, window.location.origin).toString();
  } catch (err) {
    return `${window.location.origin}/`;
  }
}

function startLoading() {
  const stages = [
    'Aligning scenario engine...',
    'Projecting milestone paths...',
    'Calculating income and lifestyle arcs...',
    'Rendering timeline cards...',
  ];
  let progress = 2;
  let stageIndex = 0;

  loadingBar.style.width = '2%';
  loadingPct.textContent = '2%';
  loadingStage.textContent = stages[0];
  loadingOverlay.classList.remove('hidden');

  loadingTimer = window.setInterval(() => {
    progress = Math.min(92, progress + Math.random() * 7 + 2);
    loadingBar.style.width = `${progress.toFixed(0)}%`;
    loadingPct.textContent = `${progress.toFixed(0)}%`;
  }, 260);

  stageTimer = window.setInterval(() => {
    stageIndex = Math.min(stages.length - 1, stageIndex + 1);
    loadingStage.textContent = stages[stageIndex];
  }, 1200);
}

function stopLoading() {
  if (loadingTimer) {
    clearInterval(loadingTimer);
    loadingTimer = null;
  }
  if (stageTimer) {
    clearInterval(stageTimer);
    stageTimer = null;
  }
  loadingBar.style.width = '100%';
  loadingPct.textContent = '100%';
  loadingStage.textContent = 'Finalizing output...';
  window.setTimeout(() => {
    loadingOverlay.classList.add('hidden');
  }, 220);
}

function formatCurrency(value) {
  const num = Number(value || 0);
  return `$${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function renderProjections(node, items, formatter) {
  clearChildren(node);
  (items || []).slice(0, 6).forEach((item) => {
    const pill = document.createElement('div');
    pill.className = 'projection-pill';
    const year = document.createElement('span');
    year.textContent = item.year;
    const value = document.createElement('strong');
    value.textContent = formatter(item.value);
    pill.appendChild(year);
    pill.appendChild(value);
    node.appendChild(pill);
  });
}

function renderTimelines(timelines) {
  clearChildren(el.timelineCards);
  (timelines || []).forEach((timeline) => {
    const card = document.createElement('div');
    card.className = 'timeline-card';

    const title = document.createElement('h4');
    title.textContent = timeline.title || 'Untitled Timeline';

    const premise = document.createElement('p');
    premise.textContent = timeline.premise || 'Alternate path details unavailable.';

    const meta = document.createElement('div');
    meta.className = 'timeline-meta';
    meta.textContent = `Regret: ${pct(timeline.regret_probability_pct)}`;

    const milestones = document.createElement('ul');
    (timeline.milestones || []).forEach((line) => {
      pushList(milestones, line);
    });

    card.appendChild(title);
    card.appendChild(premise);
    card.appendChild(meta);
    card.appendChild(milestones);

    el.timelineCards.appendChild(card);
  });
}

function renderSimulation(data) {
  const s = data.simulation;
  el.regret.textContent = pct(s.regret_probability_pct);
  el.summary.textContent = s.summary || 'Simulation complete.';
  el.contextSignal.textContent = 'LIVE';
  const sourceLabels = (s.sources || []).filter(Boolean);
  el.sourceLine.textContent = `Sources: ${sourceLabels.join(', ') || 'Gemini synthesis'}`;
  if (data.share_url) {
    activeShareUrl = data.share_url;
  }

  renderTimelines(s.timelines || []);

  const primary = (s.timelines || [])[0] || { income_projection: [], lifestyle_projection: [] };
  el.incomeSummary.textContent = s.income_projection_summary || 'Income projection unavailable.';
  el.lifestyleSummary.textContent = s.lifestyle_projection_summary || 'Lifestyle projection unavailable.';
  renderProjections(el.incomeProjection, primary.income_projection || [], formatCurrency);
  renderProjections(el.lifestyleProjection, primary.lifestyle_projection || [], (value) => `${value.toFixed(0)}/100`);

  clearChildren(el.assumptions);
  (s.assumptions || []).forEach((line) => pushList(el.assumptions, line));

  clearChildren(el.snapshots);
  (s.future_snapshots || []).forEach((line) => pushList(el.snapshots, line));

  clearChildren(el.sources);
  (s.sources || []).forEach((line) => pushList(el.sources, line));

  resultsEl.classList.remove('hidden');
}

async function refreshHistory() {
  if (!historyListEl) return;
  try {
    const res = await fetch('/api/history');
    if (!res.ok) throw new Error('History API unavailable');
    const rows = await res.json();

    clearChildren(historyListEl);
    if (!rows.length) {
      pushList(historyListEl, 'No saved timelines yet.');
      return;
    }

    rows.forEach((item) => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = item.url;
      a.className = 'history-item';
      const dt = new Date(item.created_at);
      const dateLabel = Number.isNaN(dt.getTime()) ? item.created_at : dt.toLocaleString();

      const title = document.createElement('span');
      title.className = 'history-title';
      title.textContent = item.title;

      const date = document.createElement('span');
      date.className = 'history-date';
      date.textContent = dateLabel;

      a.appendChild(title);
      a.appendChild(date);
      li.appendChild(a);
      historyListEl.appendChild(li);
    });
  } catch (err) {
    clearChildren(historyListEl);
    pushList(historyListEl, 'History could not be loaded. Check database connection.');
  }
}

async function loadFromSlugIfPresent() {
  const slug = window.location.pathname.replace(/^\/+|\/+$/g, '');
  if (!slug || slug === 'api' || slug === 'docs' || slug === 'redoc') return;

  try {
    startLoading();
    const res = await fetch(`/api/history/${encodeURIComponent(slug)}`);
    if (!res.ok) throw new Error('No saved simulation found for this URL.');
    const data = await res.json();
    activeShareUrl = `/${slug}`;
    renderSimulation(data);
    statusEl.textContent = `Loaded saved simulation: ${data.profile.career} in ${data.profile.country}.`;
  } catch (err) {
    statusEl.textContent = String(err.message || err);
  } finally {
    stopLoading();
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const formData = new FormData(form);
  const payload = {
    age: Number(formData.get('age') || 0),
    country: String(formData.get('country') || '').trim(),
    habits: String(formData.get('habits') || '').trim(),
    career: String(formData.get('career') || '').trim(),
    salary: formData.get('salary') ? Number(formData.get('salary')) : null,
    hobbies: String(formData.get('hobbies') || '').trim(),
  };

  if (!payload.age || !payload.country || !payload.habits || !payload.career || !payload.hobbies) {
    statusEl.textContent = 'Please fill in all required fields.';
    return;
  }

  submitBtn.disabled = true;
  statusEl.textContent = 'Running ParallelLife simulation...';
  startLoading();

  try {
    const response = await fetch('/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const msg = await response.text();
      throw new Error(msg || 'Request failed');
    }

    const data = await response.json();
    renderSimulation(data);
    statusEl.textContent = data.history_saved
      ? 'Simulation complete. Saved to history.'
      : `Simulation complete. History save failed: ${data.history_error || 'unknown error'}`;

    if (data.share_url) {
      history.replaceState({}, '', data.share_url);
    }
    await refreshHistory();
  } catch (err) {
    statusEl.textContent = `Request failed: ${err.message}`;
  } finally {
    stopLoading();
    submitBtn.disabled = false;
  }
});

if (refreshHistoryBtn) {
  refreshHistoryBtn.addEventListener('click', async () => {
    await refreshHistory();
  });
}

refreshHistory();
loadFromSlugIfPresent();

if (copyShareBtn) {
  copyShareBtn.addEventListener('click', async () => {
    const link = toAbsoluteUrl(activeShareUrl || window.location.pathname || '/');
    try {
      await navigator.clipboard.writeText(link);
      statusEl.textContent = 'Share link copied to clipboard.';
    } catch (err) {
      statusEl.textContent = `Could not copy link. Share manually: ${link}`;
    }
  });
}

if (exportPngBtn) {
  exportPngBtn.addEventListener('click', async () => {
    if (resultsEl.classList.contains('hidden')) {
      statusEl.textContent = 'Run a simulation first, then export PNG.';
      return;
    }
    if (typeof window.html2canvas !== 'function') {
      statusEl.textContent = 'PNG exporter library failed to load. Reload page and try again.';
      return;
    }
    try {
      const canvas = await window.html2canvas(resultsEl, {
        backgroundColor: '#eef5f7',
        scale: 2,
        useCORS: true,
      });
      const link = document.createElement('a');
      const slug = (activeShareUrl || '/timeline').replace(/^\//, '') || 'timeline';
      link.download = `${slug}-parallellife.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
      statusEl.textContent = 'PNG export complete.';
    } catch (err) {
      statusEl.textContent = `PNG export failed: ${err.message || err}`;
    }
  });
}
