/* ============================================
   ScholarAgent — Frontend Application Logic
   ============================================ */

const NODES = ['supervisor', 'scouts', 'fetcher', 'analyst', 'writer'];
const CONNECTORS = ['conn-1', 'conn-2', 'conn-3', 'conn-4'];

const NODE_LABELS = {
  supervisor: 'Planning search strategy...',
  scouts: 'Searching across databases...',
  fetcher: 'Fetching full-text papers...',
  analyst: 'Analyzing papers...',
  writer: 'Writing research report...',
};

const CARD_ICONS = {
  supervisor: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>`,
  scouts: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>`,
  fetcher: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>`,
  analyst: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" /></svg>`,
  writer: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" /></svg>`,
};

const CARD_TITLES = {
  supervisor: 'Supervisor Agent',
  scouts: 'Scout Agents',
  fetcher: 'Fetcher Agent',
  analyst: 'Analyst Agent',
  writer: 'Writer Agent',
};

let eventSource = null;

/* ---------- Query Helpers ---------- */

function setQuery(el) {
  document.getElementById('queryInput').value = el.textContent;
  document.getElementById('queryInput').focus();
}

/* ---------- Start Research ---------- */

function startResearch() {
  const input = document.getElementById('queryInput');
  const query = input.value.trim();
  if (!query) return;

  // Show pipeline, hide search hints
  document.getElementById('pipelineSection').classList.remove('hidden');
  document.getElementById('searchSection').querySelector('.search-hints').classList.add('hidden');
  document.getElementById('detailsSection').innerHTML = '';
  document.getElementById('reportSection').classList.add('hidden');
  document.getElementById('newSearch').classList.add('hidden');
  input.disabled = true;
  document.getElementById('searchBtn').disabled = true;

  // Reset pipeline visuals
  NODES.forEach(n => {
    const el = document.getElementById('node-' + n);
    el.classList.remove('active', 'completed');
    el.querySelector('.node-status').textContent = '';
  });
  CONNECTORS.forEach(c => {
    const el = document.getElementById(c);
    el.classList.remove('active', 'done');
  });
  document.getElementById('stageLabel').textContent = '';

  // Animate pipeline entrance
  const pipelineSection = document.getElementById('pipelineSection');
  pipelineSection.style.animation = 'none';
  pipelineSection.offsetHeight; // reflow
  pipelineSection.style.animation = 'fadeUp 0.5s ease-out both';

  // Activate first node
  activateNode('supervisor');

  // Open SSE connection
  const url = '/api/research?query=' + encodeURIComponent(query);
  eventSource = new EventSource(url);

  eventSource.onmessage = function (e) {
    const data = JSON.parse(e.data);
    handleEvent(data);
  };

  eventSource.onerror = function () {
    eventSource.close();
    // If no explicit error event was received, show a generic one
    const details = document.getElementById('detailsSection');
    if (!details.querySelector('.error-message')) {
      details.insertAdjacentHTML('beforeend',
        '<div class="error-message">Connection lost. The research process may still be running on the server.</div>'
      );
    }
    finishUI();
  };
}

// Allow pressing Enter to search
document.getElementById('queryInput').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') startResearch();
});

/* ---------- Event Handling ---------- */

let lastNode = null;

function handleEvent(data) {
  const event = data.event;

  if (event === 'done') {
    // Complete the last active node
    if (lastNode) completeNode(lastNode);
    eventSource.close();
    finishUI();
    return;
  }

  if (event === 'error') {
    if (lastNode) completeNode(lastNode);
    eventSource.close();
    document.getElementById('detailsSection').insertAdjacentHTML('beforeend',
      `<div class="error-message">Error: ${escapeHtml(data.message)}</div>`
    );
    finishUI();
    return;
  }

  // Agent events
  if (NODES.includes(event)) {
    // Complete previous node
    if (lastNode && lastNode !== event) {
      completeNode(lastNode);
    }

    // If this node isn't active yet, activate it
    const nodeEl = document.getElementById('node-' + event);
    if (!nodeEl.classList.contains('active') && !nodeEl.classList.contains('completed')) {
      activateNode(event);
    }

    // Build detail card
    addDetailCard(event, data);

    // Complete this node immediately (will be followed by next activation)
    completeNode(event);
    lastNode = event;
  }
}

/* ---------- Pipeline Node Control ---------- */

function activateNode(name) {
  const idx = NODES.indexOf(name);
  const nodeEl = document.getElementById('node-' + name);
  nodeEl.classList.add('active');
  nodeEl.querySelector('.node-status').innerHTML = '<span class="spinner"></span>';

  document.getElementById('stageLabel').textContent = NODE_LABELS[name] || '';

  // Activate preceding connector
  if (idx > 0) {
    document.getElementById(CONNECTORS[idx - 1]).classList.add('active');
  }
}

function completeNode(name) {
  const idx = NODES.indexOf(name);
  const nodeEl = document.getElementById('node-' + name);
  nodeEl.classList.remove('active');
  nodeEl.classList.add('completed');
  nodeEl.querySelector('.node-status').innerHTML = '&#10003;';

  // Mark connector as done
  if (idx > 0) {
    const conn = document.getElementById(CONNECTORS[idx - 1]);
    conn.classList.remove('active');
    conn.classList.add('done');
  }

  // If there's a next node, activate it
  if (idx + 1 < NODES.length) {
    const nextName = NODES[idx + 1];
    const nextEl = document.getElementById('node-' + nextName);
    if (!nextEl.classList.contains('active') && !nextEl.classList.contains('completed')) {
      activateNode(nextName);
    }
  } else {
    document.getElementById('stageLabel').textContent = 'Research complete';
  }
}

/* ---------- Detail Cards ---------- */

function addDetailCard(event, data) {
  const container = document.getElementById('detailsSection');
  const card = document.createElement('div');
  card.className = 'detail-card open';

  let badge = '';
  let body = '';

  switch (event) {
    case 'supervisor':
      badge = 'Queries';
      body = buildSupervisorBody(data);
      break;
    case 'scouts':
      badge = `${data.total} papers`;
      body = buildScoutsBody(data);
      break;
    case 'fetcher':
      badge = `${data.fetched}/${data.total} fetched`;
      body = buildFetcherBody(data);
      break;
    case 'analyst':
      badge = `${data.analyzed} analyzed`;
      body = buildAnalystBody(data);
      break;
    case 'writer':
      badge = 'Complete';
      body = '<div class="card-content"><p>Report generated successfully.</p></div>';
      break;
  }

  card.innerHTML = `
    <div class="detail-card-header" onclick="toggleCard(this)">
      <div class="card-icon ${event}">${CARD_ICONS[event]}</div>
      <span class="card-title">${CARD_TITLES[event]}</span>
      <span class="card-badge">${badge}</span>
      <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 9l-7 7-7-7"/></svg>
    </div>
    <div class="detail-card-body">${body}</div>
  `;

  // Stagger animation
  card.style.animationDelay = '0.05s';
  container.appendChild(card);

  // Scroll into view smoothly
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function toggleCard(headerEl) {
  headerEl.parentElement.classList.toggle('open');
}

function buildSupervisorBody(data) {
  const queries = data.queries || {};
  let html = '<div class="card-content">';
  for (const [source, query] of Object.entries(queries)) {
    html += `<div style="margin-bottom:0.4rem"><strong style="color:var(--text);text-transform:capitalize">${source}</strong>: <span class="tag">${escapeHtml(query)}</span></div>`;
  }
  html += '</div>';
  return html;
}

function buildScoutsBody(data) {
  const sources = data.sources || {};
  const total = data.total || 0;
  let html = '<div class="card-content">';

  // Source bars
  for (const [source, count] of Object.entries(sources)) {
    const pct = total > 0 ? (count / total) * 100 : 0;
    html += `
      <div class="source-row">
        <span style="width:110px;text-transform:capitalize;color:var(--text)">${source.replace('_', ' ')}</span>
        <span style="width:28px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:0.75rem">${count}</span>
        <div style="flex:1"><div class="source-bar ${source}" style="width:${pct}%"></div></div>
      </div>`;
  }

  // Paper list (collapsible)
  if (data.papers && data.papers.length > 0) {
    html += '<div style="margin-top:0.75rem;border-top:1px solid var(--border);padding-top:0.5rem">';
    for (const p of data.papers) {
      html += `<div class="paper-item">
        <div class="paper-title"><a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">${escapeHtml(p.title)}</a></div>
        <div class="paper-meta">${escapeHtml(p.source)}</div>
      </div>`;
    }
    html += '</div>';
  }

  html += '</div>';
  return html;
}

function buildFetcherBody(data) {
  const pct = data.total > 0 ? (data.fetched / data.total) * 100 : 0;
  return `<div class="card-content">
    <p>Successfully retrieved full text for <strong style="color:var(--text)">${data.fetched}</strong> out of <strong style="color:var(--text)">${data.total}</strong> papers.</p>
    <div style="margin-top:0.5rem;height:8px;background:var(--border);border-radius:4px;overflow:hidden">
      <div style="width:${pct}%;height:100%;background:var(--amber);border-radius:4px;transition:width 0.6s ease"></div>
    </div>
  </div>`;
}

function buildAnalystBody(data) {
  let html = '<div class="card-content">';
  html += `<p>Analyzed <strong style="color:var(--text)">${data.analyzed}</strong> papers — sorted by relevance:</p>`;

  if (data.top_papers && data.top_papers.length > 0) {
    html += '<div style="margin-top:0.5rem;border-top:1px solid var(--border);padding-top:0.5rem">';
    for (const p of data.top_papers) {
      const scoreColor = p.score >= 70 ? 'var(--green)' : p.score >= 40 ? 'var(--amber)' : 'var(--rose)';
      const scorePct = Math.min(p.score, 100);
      const studyInfo = p.study_type ? ` · ${p.study_type}` : '';
      const evidenceInfo = p.evidence_level ? ` · ${p.evidence_level}` : '';
      html += `<div class="paper-item">
        <div class="paper-title"><a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">${escapeHtml(p.title)}</a></div>
        <div class="paper-meta">
          Relevance: <strong style="color:${scoreColor}">${p.score}</strong>/100
          <span class="score-bar-bg"><span class="score-bar-fill" style="width:${scorePct}%;background:${scoreColor}"></span></span>
          <span style="margin-left:0.5rem;color:var(--text-dim)">${escapeHtml(studyInfo)}${escapeHtml(evidenceInfo)}</span>
        </div>
        ${p.findings ? `<div class="paper-meta" style="margin-top:0.2rem;color:var(--text-dim)">${escapeHtml(truncate(p.findings, 180))}</div>` : ''}
      </div>`;
    }
    html += '</div>';
  }

  html += '</div>';
  return html;
}

/* ---------- Finish / Reset ---------- */

function finishUI() {
  document.getElementById('queryInput').disabled = false;
  document.getElementById('searchBtn').disabled = false;
  document.getElementById('newSearch').classList.remove('hidden');
}

function resetUI() {
  document.getElementById('pipelineSection').classList.add('hidden');
  document.getElementById('detailsSection').innerHTML = '';
  document.getElementById('reportSection').classList.add('hidden');
  document.getElementById('newSearch').classList.add('hidden');
  document.getElementById('searchSection').querySelector('.search-hints').classList.remove('hidden');
  document.getElementById('queryInput').value = '';
  document.getElementById('queryInput').disabled = false;
  document.getElementById('searchBtn').disabled = false;
  document.getElementById('queryInput').focus();
  lastNode = null;

  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ---------- Report Rendering ---------- */

function showReport(markdown) {
  const section = document.getElementById('reportSection');
  const content = document.getElementById('reportContent');

  // Render markdown to HTML
  if (typeof marked !== 'undefined') {
    content.innerHTML = marked.parse(markdown);
  } else {
    // Fallback: render as preformatted text
    content.innerHTML = `<pre style="white-space:pre-wrap">${escapeHtml(markdown)}</pre>`;
  }

  section.classList.remove('hidden');
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* Override writer event handling to show report */
const _origHandleEvent = handleEvent;
handleEvent = function (data) {
  if (data.event === 'writer' && data.report) {
    // Show report after the pipeline completes
    setTimeout(() => showReport(data.report), 400);
  }
  _origHandleEvent(data);
};

/* ---------- Utilities ---------- */

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function truncate(text, max) {
  if (!text || text.length <= max) return text;
  return text.slice(0, max) + '...';
}
