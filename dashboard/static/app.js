// === Apex Agent dashboard ===

// === API helper ===
async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${path}`);
  return r.json();
}

function escapeHTML(s) {
  return String(s ?? '').replace(/[<>&"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));
}

function fmtTs(t) {
  if (!t) return '—';
  const d = new Date(t * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
function fmtDate(t) {
  if (!t) return '—';
  return new Date(t * 1000).toLocaleDateString();
}
function fmtCost(c) { return '$' + (c || 0).toFixed(4); }
function fmtNum(n) { return new Intl.NumberFormat().format(n || 0); }

// === Tab switching ===
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    document.getElementById('tab-' + tab).classList.add('active');
    loadTab(tab);
  });
});

// === Status bar ===
async function refreshStatus() {
  try {
    const s = await api('/api/status');
    document.getElementById('status-model').textContent = s.model.replace('claude-', '');
    document.getElementById('status-tools').textContent = s.tools_count;
    const h = Math.floor(s.uptime_s / 3600), m = Math.floor((s.uptime_s % 3600) / 60);
    document.getElementById('status-uptime').textContent = `${h}h ${m}m`;
  } catch (e) {}
}
setInterval(refreshStatus, 5000);
refreshStatus();

// === WebSocket live feed ===
const wsIndicator = document.getElementById('ws-indicator');
const feed = document.getElementById('event-feed');
const overviewFeed = document.getElementById('overview-feed');
let ws;
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  ws.onopen = () => { wsIndicator.textContent = '● live'; wsIndicator.className = 'brand-sub ws-on'; };
  ws.onclose = () => {
    wsIndicator.textContent = '● offline'; wsIndicator.className = 'brand-sub ws-off';
    setTimeout(connectWS, 3000);
  };
  ws.onmessage = ev => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'event') addFeedItem(msg);
    if (msg.type === 'snapshot' && msg.data?.events_recent) {
      msg.data.events_recent.forEach(e => addFeedItem(e));
    }
  };
  setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 25000);
}
function addFeedItem(msg) {
  const row = (() => {
    const div = document.createElement('div');
    div.className = 'feed-item';
    div.innerHTML = `
      <span class="ts">${fmtTs(msg.ts)}</span>
      <span class="source">${escapeHTML(msg.source || 'event')}</span>
      <span class="content">${escapeHTML(msg.content || '')}</span>`;
    return div;
  });
  feed.prepend(row());
  while (feed.children.length > 250) feed.removeChild(feed.lastChild);
  overviewFeed.prepend(row());
  while (overviewFeed.children.length > 8) overviewFeed.removeChild(overviewFeed.lastChild);
}
connectWS();

// === Tab loaders ===
async function loadTab(tab) {
  const fns = {
    overview: loadOverview,
    goals: loadGoals,
    memory: loadMemory,
    graph: loadGraph,
    reflections: loadReflections,
    telemetry: loadTelemetry,
    replay: loadReplay,
    schedule: loadTasks,
    subagents: loadSubagents,
    knowledge: loadKB,
    selfmod: loadSelfMod,
    phone: loadPhone,
  };
  if (fns[tab]) try { await fns[tab](); } catch (e) { console.error('loadTab', tab, e); }
}
loadTab('overview');

// ============== OVERVIEW ==============
let overviewCostChart = null;
async function loadOverview() {
  try {
    const [tel, goals, mems, tasks, refl, ents] = await Promise.all([
      api('/api/telemetry?days=7'),
      api('/api/goals?active_only=true'),
      api('/api/memories?limit=500'),
      api('/api/tasks'),
      api('/api/reflections?status=pending'),
      api('/api/entities?limit=500'),
    ]);
    document.getElementById('ov-cost').textContent = fmtCost(tel.total_cost_usd);
    document.getElementById('ov-cost-meta').textContent = `${fmtNum(tel.total_input_tokens + tel.total_output_tokens)} tokens`;
    document.getElementById('ov-cache').textContent = (tel.cache_hit_rate * 100).toFixed(1) + '%';
    document.getElementById('ov-cache-bar').style.width = (tel.cache_hit_rate * 100) + '%';
    document.getElementById('ov-calls').textContent = fmtNum(tel.total_calls);
    document.getElementById('ov-goals').textContent = goals.length;
    document.getElementById('ov-mems').textContent = mems.length;
    document.getElementById('ov-ents').textContent = (ents.nodes || ents).length || 0;
    document.getElementById('ov-refl').textContent = refl.length;
    document.getElementById('ov-tasks').textContent = tasks.length;

    // Cost / day chart
    const ctx = document.getElementById('overview-cost-chart').getContext('2d');
    if (overviewCostChart) overviewCostChart.destroy();
    const labels = tel.by_day.map(d => new Date(d.day * 1000).toLocaleDateString([], {month:'short', day:'numeric'}));
    const data = tel.by_day.map(d => d.cost_usd);
    overviewCostChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Cost (USD)',
          data,
          backgroundColor: '#6cf', borderRadius: 4, maxBarThickness: 36,
        }]
      },
      options: chartOpts({ y: { ticks: { callback: v => '$' + v } } })
    });
  } catch (e) { console.error('overview', e); }
}

function chartOpts(scaleOverrides = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: '#8892a6', font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: '#5e6878', font: { size: 11 } }, grid: { color: '#1c2230' } },
      y: { ticks: { color: '#5e6878', font: { size: 11 }, ...(scaleOverrides.y?.ticks || {}) }, grid: { color: '#1c2230' }, beginAtZero: true },
    }
  };
}

// ============== GOALS ==============
async function loadGoals() {
  const goals = await api('/api/goals?active_only=false');
  const wrap = document.getElementById('goals-list');
  wrap.innerHTML = goals.map(g => `
    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title"><span class="badge horizon">${g.horizon}</span> ${escapeHTML(g.title)} <span class="status-${g.status}">[${g.status}]</span></div>
          ${g.description ? `<div class="card-meta">${escapeHTML(g.description)}</div>` : ''}
          ${g.deadline ? `<div class="card-meta">Deadline: ${new Date(g.deadline*1000).toDateString()}</div>` : ''}
          <div class="card-meta">${g.recent_progress.length} progress notes</div>
        </div>
      </div>
      <div class="actions">
        <button onclick="updateGoal(${g.id}, 'done')">Mark done</button>
        <button onclick="updateGoal(${g.id}, 'paused')">Pause</button>
        <button onclick="addProgress(${g.id})">Add note</button>
      </div>
    </div>`).join('') || '<div class="empty-state">No goals yet.</div>';
}
async function updateGoal(id, status) { await api(`/api/goals/${id}`, { method: 'PATCH', body: { status } }); loadGoals(); }
async function addProgress(id) {
  const note = prompt('Progress note:'); if (!note) return;
  await api(`/api/goals/${id}`, { method: 'PATCH', body: { progress_note: note } });
  loadGoals();
}
document.getElementById('goal-form').addEventListener('submit', async e => {
  e.preventDefault(); const f = e.target;
  await api('/api/goals', { method: 'POST', body: {
    title: f.title.value, description: f.description.value,
    horizon: f.horizon.value, deadline_iso: f.deadline_iso.value || null,
  }});
  f.reset(); loadGoals();
});

// ============== MEMORY ==============
async function loadMemory() {
  const q = document.getElementById('memory-search').value;
  const mems = await api('/api/memories?q=' + encodeURIComponent(q));
  const tbody = document.querySelector('#memory-table tbody');
  tbody.innerHTML = mems.map(m => `
    <tr>
      <td>${m.id}</td>
      <td><span class="badge horizon">${m.kind}</span></td>
      <td>${'★'.repeat(Math.min(m.importance, 10))}</td>
      <td>${escapeHTML(m.content)}</td>
      <td><button onclick="forgetMem(${m.id})" style="background:var(--danger);color:#fff;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px">Delete</button></td>
    </tr>`).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--text-dim);padding:20px">No memories.</td></tr>';
}
async function forgetMem(id) { await api('/api/memories/' + id, { method: 'DELETE' }); loadMemory(); }
document.getElementById('memory-refresh').addEventListener('click', loadMemory);
document.getElementById('memory-search').addEventListener('keypress', e => { if (e.key === 'Enter') loadMemory(); });

// ============== KNOWLEDGE GRAPH ==============
let visNetwork = null;
const KIND_COLORS = {
  person: '#6cf', project: '#3ddc97', place: '#ffb547', concept: '#8892a6',
  tool: '#8a7cff', file: '#5e6878', event: '#ff6a6a', org: '#d29922',
};

async function loadGraph() {
  await renderGraph();
}

async function renderGraph(filter = {}) {
  const kindFilter = document.getElementById('graph-kind-filter')?.value || '';
  const search = (document.getElementById('graph-search')?.value || '').trim();

  let data;
  if (search) {
    try { data = await api('/api/entities/query?name=' + encodeURIComponent(search) + '&hops=2'); }
    catch { data = { nodes: [], edges: [] }; }
    if (data.error) { document.getElementById('graph-side').innerHTML = `<div class="graph-side-empty">${escapeHTML(data.error)}</div>`; }
  } else if (kindFilter) {
    const ents = await api('/api/entities?kind=' + kindFilter);
    data = { nodes: ents, edges: [] };
  } else {
    data = await api('/api/entities?limit=100');
  }

  const nodes = (data.nodes || []).map(n => ({
    id: n.id,
    label: n.name,
    title: `${n.kind}: ${n.name}`,
    color: { background: KIND_COLORS[n.kind] || '#8892a6', border: '#11161f', highlight: { background: KIND_COLORS[n.kind] || '#8892a6', border: '#fff' } },
    font: { color: '#fff', size: 13 },
    shape: 'dot', size: 10 + (n.importance || 5) * 1.5,
    _entity: n,
  }));
  const edges = (data.edges || []).map(e => ({
    id: e.id, from: e.from_id, to: e.to_id, label: e.kind,
    color: { color: '#2e3648', highlight: '#6cf' },
    font: { color: '#5e6878', size: 10, strokeWidth: 0 },
    arrows: { to: { enabled: true, scaleFactor: 0.6 } }, smooth: { type: 'continuous' },
  }));

  const container = document.getElementById('graph-canvas');
  if (visNetwork) visNetwork.destroy();
  visNetwork = new vis.Network(container, { nodes, edges }, {
    physics: { stabilization: true, barnesHut: { gravitationalConstant: -8000, springLength: 120 } },
    interaction: { hover: true, tooltipDelay: 200 },
    nodes: { borderWidth: 2 },
  });
  visNetwork.on('selectNode', params => {
    const node = nodes.find(n => n.id === params.nodes[0]);
    if (node) showEntitySide(node._entity);
  });
}

function showEntitySide(entity) {
  document.getElementById('graph-side').innerHTML = `
    <h4>${escapeHTML(entity.name)}</h4>
    <div class="meta"><span class="badge horizon">${entity.kind}</span> · importance ${entity.importance}</div>
    <div class="meta">Last seen: ${fmtDate(entity.last_seen)}</div>
    <div class="meta">Created: ${fmtDate(entity.created_at)}</div>
    ${Object.keys(entity.properties || {}).length ? `<pre>${escapeHTML(JSON.stringify(entity.properties, null, 2))}</pre>` : ''}
    <div style="margin-top:10px"><button onclick="deleteEntity(${entity.id})" style="background:var(--danger);color:#fff;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-size:12px">Delete entity</button></div>
  `;
}
async function deleteEntity(id) {
  if (!confirm('Delete this entity and its relations?')) return;
  await api('/api/entities/' + id, { method: 'DELETE' });
  renderGraph();
  document.getElementById('graph-side').innerHTML = '<div class="graph-side-empty">Click a node to inspect.</div>';
}
document.getElementById('graph-refresh')?.addEventListener('click', () => {
  document.getElementById('graph-search').value = '';
  document.getElementById('graph-kind-filter').value = '';
  renderGraph();
});
document.getElementById('graph-search-btn')?.addEventListener('click', () => renderGraph());
document.getElementById('graph-search')?.addEventListener('keypress', e => { if (e.key === 'Enter') renderGraph(); });
document.getElementById('graph-kind-filter')?.addEventListener('change', () => renderGraph());

// ============== REFLECTIONS ==============
let reflectionsStatus = 'pending';
async function loadReflections() {
  const refl = await api('/api/reflections?status=' + reflectionsStatus);
  const wrap = document.getElementById('reflections-list');
  wrap.innerHTML = refl.map(r => `
    <div class="card">
      <div class="card-head">
        <div style="flex:1">
          <div class="card-title"><span class="badge kind-${r.kind}">${r.kind}</span> ${escapeHTML(r.content)}</div>
          <div class="card-meta">Confidence: ${(r.confidence * 100).toFixed(0)}% · ${fmtDate(r.ts)} · ${r.status}</div>
          <div class="confidence-bar"><div class="confidence-bar-fill" style="width:${r.confidence * 100}%"></div></div>
          ${r.action && Object.keys(r.action).length ? `<details style="margin-top:8px"><summary style="cursor:pointer;font-size:12px;color:var(--text-mute)">Action</summary><pre style="margin-top:6px;background:var(--bg-3);padding:8px;border-radius:4px;font-size:11.5px;color:var(--text-mute)">${escapeHTML(JSON.stringify(r.action, null, 2))}</pre></details>` : ''}
        </div>
      </div>
      ${r.status === 'pending' ? `
        <div class="actions">
          <button class="accept" onclick="applyRefl(${r.id}, true)">Accept</button>
          <button class="reject" onclick="applyRefl(${r.id}, false)">Reject</button>
        </div>` : ''}
    </div>`).join('') || `<div class="empty-state">No ${reflectionsStatus} reflections.</div>`;
}
async function applyRefl(id, accept) {
  await api(`/api/reflections/${id}/apply`, { method: 'POST', body: { accept } });
  loadReflections();
}
['pending','applied','rejected'].forEach(s => {
  document.getElementById('refl-tab-' + s).addEventListener('click', e => {
    document.querySelectorAll('#tab-reflections .filter-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    reflectionsStatus = s;
    loadReflections();
  });
});
document.getElementById('refl-run').addEventListener('click', async () => {
  document.getElementById('refl-run').textContent = 'Running...';
  document.getElementById('refl-run').disabled = true;
  try {
    const r = await api('/api/reflections/run', { method: 'POST', body: { hours: 24 } });
    alert(`Created ${r.created} reflections, auto-applied ${r.applied}, pending ${r.pending || 0}.`);
  } catch (e) { alert('Failed: ' + e.message); }
  document.getElementById('refl-run').textContent = 'Run consolidation now';
  document.getElementById('refl-run').disabled = false;
  loadReflections();
});

// ============== TELEMETRY ==============
let telCostChart = null, telModelChart = null;
async function loadTelemetry() {
  const days = parseInt(document.getElementById('tel-window').value);
  const t = await api('/api/telemetry?days=' + days);
  document.getElementById('tel-cost').textContent = fmtCost(t.total_cost_usd);
  document.getElementById('tel-calls').textContent = fmtNum(t.total_calls);
  document.getElementById('tel-cache').textContent = (t.cache_hit_rate * 100).toFixed(1) + '%';
  document.getElementById('tel-out').textContent = fmtNum(t.total_output_tokens);

  if (telCostChart) telCostChart.destroy();
  telCostChart = new Chart(document.getElementById('tel-cost-chart').getContext('2d'), {
    type: 'bar',
    data: {
      labels: t.by_day.map(d => new Date(d.day * 1000).toLocaleDateString([], {month:'short', day:'numeric'})),
      datasets: [{ label: 'Cost (USD)', data: t.by_day.map(d => d.cost_usd), backgroundColor: '#6cf', borderRadius: 4 }],
    },
    options: chartOpts({ y: { ticks: { callback: v => '$' + v } } })
  });

  if (telModelChart) telModelChart.destroy();
  telModelChart = new Chart(document.getElementById('tel-model-chart').getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: t.by_model.map(m => m.model.replace('claude-', '')),
      datasets: [{
        data: t.by_model.map(m => m.input_tokens + m.cache_read_tokens + m.output_tokens),
        backgroundColor: ['#6cf', '#8a7cff', '#3ddc97', '#ffb547', '#ff6a6a'],
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { color: '#8892a6', font: { size: 11 } } } },
    }
  });

  const tbody = document.querySelector('#tel-model-table tbody');
  tbody.innerHTML = t.by_model.map(m => `
    <tr>
      <td>${m.model.replace('claude-', '')}</td>
      <td>${fmtNum(m.calls)}</td>
      <td>${fmtNum(m.input_tokens)}</td>
      <td>${fmtNum(m.cache_read_tokens)}</td>
      <td>${fmtNum(m.output_tokens)}</td>
      <td>${m.avg_latency_ms} ms</td>
      <td>${fmtCost(m.cost_usd)}</td>
    </tr>`).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--text-dim);padding:20px">No usage yet.</td></tr>';
}
document.getElementById('tel-refresh').addEventListener('click', loadTelemetry);
document.getElementById('tel-window').addEventListener('change', loadTelemetry);

// ============== REPLAY ==============
async function loadReplay() {
  const sessions = await api('/api/telemetry/sessions');
  const list = document.getElementById('replay-sessions');
  list.innerHTML = sessions.map(s => `
    <div class="replay-session-item" onclick="showReplay(${s.id})" id="sess-${s.id}">
      <div><strong>Session #${s.id}</strong></div>
      <div class="sess-meta">${fmtDate(s.started_at)} · ${s.calls} calls · ${fmtCost(s.cost_usd)}</div>
    </div>`).join('') || '<div class="empty-state">No sessions.</div>';
}
async function showReplay(sessionId) {
  document.querySelectorAll('.replay-session-item').forEach(el => el.classList.remove('active'));
  document.getElementById('sess-' + sessionId)?.classList.add('active');
  const r = await api('/api/replay/' + sessionId);
  const detail = document.getElementById('replay-detail');
  const turns = (r.turns || []).map(t => {
    const content = typeof t.content === 'object' ? JSON.stringify(t.content, null, 2) : String(t.content);
    const tools = (t.tool_calls || []).length ? `<div class="card-meta" style="margin-top:4px">tools: ${t.tool_calls.map(tc => tc.name || tc.tool || '?').join(', ')}</div>` : '';
    return `
      <div class="replay-turn role-${t.role}">
        <div class="turn-head"><span class="turn-role">${t.role}</span><span class="turn-ts">${fmtTs(t.ts)}</span></div>
        <pre>${escapeHTML(content)}</pre>
        ${tools}
      </div>`;
  }).join('');
  const usageRows = (r.usage || []).map(u => `
    <tr>
      <td>${u.turn_index}</td><td>${u.call_site}</td><td>${u.model.replace('claude-', '')}</td>
      <td>${fmtNum(u.input_tokens)} / ${fmtNum(u.cache_read_tokens)} / ${fmtNum(u.output_tokens)}</td>
      <td>${u.latency_ms} ms</td><td>${fmtCost(u.cost_usd)}</td>
    </tr>`).join('');
  detail.innerHTML = `
    <h3 style="margin-top:0">Session #${r.session.id}</h3>
    <div class="card-meta">${fmtDate(r.session.started_at)} → ${r.session.ended_at ? fmtDate(r.session.ended_at) : 'open'} · ${(r.usage || []).length} API calls</div>
    <h4 style="margin-top:20px">Per-call usage</h4>
    <table class="data-table">
      <thead><tr><th>Turn</th><th>Site</th><th>Model</th><th>In / Cache / Out</th><th>Latency</th><th>Cost</th></tr></thead>
      <tbody>${usageRows || '<tr><td colspan="6" style="text-align:center;color:var(--text-dim)">No usage rows.</td></tr>'}</tbody>
    </table>
    <h4 style="margin-top:24px">Turns</h4>
    ${turns || '<div class="empty-state">No turn data captured for this session.</div>'}
  `;
}

// ============== SCHEDULE ==============
async function loadTasks() {
  const tasks = await api('/api/tasks');
  const wrap = document.getElementById('tasks-list');
  wrap.innerHTML = tasks.map(t => `
    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">${escapeHTML(t.description)}</div>
          <div class="card-meta">${t.trigger_type}: <code>${escapeHTML(JSON.stringify(t.trigger_params))}</code></div>
          <div class="card-meta">Runs: ${t.run_count} · Last: ${t.last_run ? new Date(t.last_run*1000).toLocaleString() : 'never'}</div>
        </div>
      </div>
      <div class="actions"><button onclick="cancelTask('${t.id}')">Cancel</button></div>
    </div>`).join('') || '<div class="empty-state">No scheduled tasks.</div>';
}
async function cancelTask(id) { await api('/api/tasks/' + id, { method: 'DELETE' }); loadTasks(); }
document.getElementById('task-form').addEventListener('submit', async e => {
  e.preventDefault(); const f = e.target;
  let params; try { params = JSON.parse(f.trigger_params.value); }
  catch { alert('trigger_params must be valid JSON'); return; }
  await api('/api/tasks', { method: 'POST', body: {
    description: f.description.value, trigger_type: f.trigger_type.value, trigger_params: params,
  }});
  f.reset(); loadTasks();
});

// ============== SUB-AGENTS ==============
async function loadSubagents() {
  const subs = await api('/api/subagents');
  const wrap = document.getElementById('subagents-list');
  const entries = Object.entries(subs);
  wrap.innerHTML = entries.map(([id, s]) => `
    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">${id} <span class="badge horizon">${s.role}</span> <span class="status-${s.status}">[${s.status}]</span></div>
          <div class="card-meta">${escapeHTML(s.task)}</div>
        </div>
      </div>
      ${s.result_preview ? `<pre style="white-space:pre-wrap;font-size:12px;margin-top:8px;background:var(--bg-3);padding:10px;border-radius:6px;color:var(--text-mute)">${escapeHTML(s.result_preview)}</pre>` : ''}
      ${s.error ? `<div class="status-error" style="margin-top:6px">${escapeHTML(s.error)}</div>` : ''}
    </div>`).join('') || '<div class="empty-state">No sub-agents running.</div>';
}

// ============== KNOWLEDGE BASE ==============
async function loadKB() {
  try {
    const s = await api('/api/knowledge/stats');
    document.getElementById('kb-stats').textContent = `Indexed: ${s.files} files · ${s.chunks} chunks`;
  } catch { document.getElementById('kb-stats').textContent = '—'; }
}
document.getElementById('kb-reindex-form').addEventListener('submit', async e => {
  e.preventDefault(); const f = e.target;
  const paths = f.paths.value.split(',').map(s => s.trim()).filter(Boolean);
  document.getElementById('kb-stats').textContent = 'Indexing...';
  const r = await api('/api/knowledge/reindex', { method: 'POST', body: { paths, force: f.force.checked }});
  alert(r.result); loadKB();
});
document.getElementById('kb-search-btn').addEventListener('click', async () => {
  const q = document.getElementById('kb-search-input').value; if (!q) return;
  const results = await api('/api/knowledge/search?q=' + encodeURIComponent(q));
  document.getElementById('kb-results').innerHTML = results.map(r => `
    <div class="card">
      <div class="card-meta">${escapeHTML(r.path)} #${r.chunk_index} — score ${r.score}</div>
      <pre style="white-space:pre-wrap;font-size:12.5px;background:var(--bg-3);padding:10px;border-radius:6px;margin-top:6px">${escapeHTML(r.content)}</pre>
    </div>`).join('') || '<div class="empty-state">No matches.</div>';
});

// ============== SELF-MOD ==============
async function loadSelfMod() {
  const s = await api('/api/selfmod');
  document.getElementById('selfmod-state').innerHTML = `
    <div class="panel" style="margin-bottom:14px">
      <div class="panel-head"><h3>Prompt overlay</h3><span class="panel-sub">${s.prompt_addition_chars} chars</span></div>
      ${s.prompt_addition_preview ? `<pre style="white-space:pre-wrap;font-size:12.5px;color:var(--text-mute);margin:0">${escapeHTML(s.prompt_addition_preview)}</pre>` : '<div class="card-meta">(empty)</div>'}
      <div class="card-meta" style="margin-top:10px">Dynamic tools: ${s.dynamic_tools.join(', ') || '(none)'}</div>
    </div>`;
}
document.getElementById('prompt-form').addEventListener('submit', async e => {
  e.preventDefault(); const f = e.target;
  await api('/api/selfmod/prompt', { method: 'POST', body: { addition: f.addition.value, replace: f.replace.checked }});
  f.reset(); loadSelfMod();
});
document.getElementById('revert-btn').addEventListener('click', async () => {
  if (!confirm('Revert ALL self-modifications?')) return;
  await api('/api/selfmod/revert', { method: 'POST', body: {} });
  loadSelfMod();
});

// ============== PHONE ==============
async function loadPhone() {
  try {
    const p = await api('/api/phone/status');
    document.getElementById('phone-state').innerHTML = `
      <div class="panel-head"><h3>Status</h3><span class="${p.configured ? 'status-active' : 'status-failed'}">${p.configured ? '● Configured' : '● Not configured'}</span></div>
      <div class="card-meta">From: ${p.from_number || '—'}</div>
      <div class="card-meta">Allowed inbound: ${(p.allowed_numbers || []).join(', ') || '(any)'}</div>
    `;
  } catch (e) {
    document.getElementById('phone-state').innerHTML = '<div class="card-meta">Unavailable.</div>';
  }
}
document.getElementById('sms-form').addEventListener('submit', async e => {
  e.preventDefault(); const f = e.target;
  document.getElementById('sms-result').textContent = 'Sending...';
  try {
    const r = await api('/api/phone/sms', { method: 'POST', body: { to: f.to.value, body: f.body.value }});
    document.getElementById('sms-result').textContent = r.result;
  } catch (err) { document.getElementById('sms-result').textContent = err.message; }
});

// Refresh sub-agents periodically
setInterval(() => {
  if (document.querySelector('.nav-btn.active')?.dataset.tab === 'subagents') loadSubagents();
}, 3000);

// Refresh overview every 30s
setInterval(() => {
  if (document.querySelector('.nav-btn.active')?.dataset.tab === 'overview') loadOverview();
}, 30000);
