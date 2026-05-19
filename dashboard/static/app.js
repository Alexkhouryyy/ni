// === Tab switching ===
document.querySelectorAll('nav.tabs button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('nav.tabs button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    loadTab(btn.dataset.tab);
  });
});

// === API helper ===
async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  return r.json();
}

// === Status bar ===
async function refreshStatus() {
  try {
    const s = await api('/api/status');
    document.getElementById('status-model').textContent = s.model;
    document.getElementById('status-tools').textContent = `${s.tools_count} tools`;
    const h = Math.floor(s.uptime_s / 3600), m = Math.floor((s.uptime_s % 3600) / 60);
    document.getElementById('status-uptime').textContent = `up ${h}h ${m}m`;
  } catch (e) {}
}
setInterval(refreshStatus, 5000);
refreshStatus();

// === WebSocket live feed ===
const wsIndicator = document.getElementById('ws-indicator');
const feed = document.getElementById('event-feed');
let ws;
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  ws.onopen = () => { wsIndicator.textContent = 'live'; wsIndicator.className = 'ws-on'; };
  ws.onclose = () => {
    wsIndicator.textContent = 'offline'; wsIndicator.className = 'ws-off';
    setTimeout(connectWS, 3000);
  };
  ws.onmessage = ev => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'event') addFeedItem(msg);
    if (msg.type === 'snapshot' && msg.data?.events_recent) {
      msg.data.events_recent.forEach(e => addFeedItem({ ts: e.ts, source: e.source, content: e.content }));
    }
  };
  // ping keep-alive
  setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 25000);
}
function addFeedItem(msg) {
  const div = document.createElement('div');
  div.className = 'feed-item';
  const time = new Date(msg.ts * 1000).toLocaleTimeString();
  div.innerHTML = `<span class="ts">${time}</span><span class="source">${msg.source}</span>${escapeHTML(msg.content || '')}`;
  feed.prepend(div);
  while (feed.children.length > 200) feed.removeChild(feed.lastChild);
}
function escapeHTML(s) { return String(s).replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c])); }
connectWS();

// === Tab loaders ===
async function loadTab(tab) {
  if (tab === 'goals') return loadGoals();
  if (tab === 'memory') return loadMemory();
  if (tab === 'schedule') return loadTasks();
  if (tab === 'knowledge') return loadKB();
  if (tab === 'subagents') return loadSubagents();
  if (tab === 'selfmod') return loadSelfMod();
}

// === Goals ===
async function loadGoals() {
  const goals = await api('/api/goals?active_only=false');
  const wrap = document.getElementById('goals-list');
  wrap.innerHTML = goals.map(g => `
    <div class="card">
      <div><span class="horizon">${g.horizon}</span> <strong>${escapeHTML(g.title)}</strong> <span class="status-${g.status}">[${g.status}]</span></div>
      ${g.description ? `<div class="meta">${escapeHTML(g.description)}</div>` : ''}
      ${g.deadline ? `<div class="meta">Deadline: ${new Date(g.deadline*1000).toDateString()}</div>` : ''}
      <div class="meta">Recent progress: ${g.recent_progress.length} notes</div>
      <div class="actions">
        <button onclick="updateGoal(${g.id}, 'done')">Mark done</button>
        <button onclick="updateGoal(${g.id}, 'paused')">Pause</button>
        <button onclick="addProgress(${g.id})">Add note</button>
      </div>
    </div>
  `).join('') || '<p>No goals yet. Set one above.</p>';
}
async function updateGoal(id, status) {
  await api(`/api/goals/${id}`, { method: 'PATCH', body: { status } });
  loadGoals();
}
async function addProgress(id) {
  const note = prompt('Progress note:');
  if (!note) return;
  await api(`/api/goals/${id}`, { method: 'PATCH', body: { progress_note: note } });
  loadGoals();
}
document.getElementById('goal-form').addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target;
  await api('/api/goals', { method: 'POST', body: {
    title: f.title.value,
    description: f.description.value,
    horizon: f.horizon.value,
    deadline_iso: f.deadline_iso.value || null,
  }});
  f.reset();
  loadGoals();
});

// === Memory ===
async function loadMemory() {
  const q = document.getElementById('memory-search').value;
  const mems = await api('/api/memories?q=' + encodeURIComponent(q));
  const tbody = document.querySelector('#memory-table tbody');
  tbody.innerHTML = mems.map(m => `
    <tr>
      <td>${m.id}</td><td>${m.kind}</td><td>${m.importance}</td>
      <td>${escapeHTML(m.content)}</td>
      <td><button onclick="forgetMem(${m.id})">Delete</button></td>
    </tr>
  `).join('') || '<tr><td colspan="5">No memories.</td></tr>';
}
async function forgetMem(id) {
  await api('/api/memories/' + id, { method: 'DELETE' });
  loadMemory();
}
document.getElementById('memory-refresh').addEventListener('click', loadMemory);
document.getElementById('memory-search').addEventListener('keypress', e => { if (e.key === 'Enter') loadMemory(); });

// === Scheduler ===
async function loadTasks() {
  const tasks = await api('/api/tasks');
  const wrap = document.getElementById('tasks-list');
  wrap.innerHTML = tasks.map(t => `
    <div class="card">
      <div><strong>${escapeHTML(t.description)}</strong></div>
      <div class="meta">${t.trigger_type}: ${JSON.stringify(t.trigger_params)}</div>
      <div class="meta">Runs: ${t.run_count} | Last: ${t.last_run ? new Date(t.last_run*1000).toLocaleString() : 'never'}</div>
      <div class="actions">
        <button onclick="cancelTask('${t.id}')">Cancel</button>
      </div>
    </div>
  `).join('') || '<p>No scheduled tasks.</p>';
}
async function cancelTask(id) {
  await api('/api/tasks/' + id, { method: 'DELETE' });
  loadTasks();
}
document.getElementById('task-form').addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target;
  let params;
  try { params = JSON.parse(f.trigger_params.value); }
  catch { alert('trigger_params must be valid JSON'); return; }
  await api('/api/tasks', { method: 'POST', body: {
    description: f.description.value,
    trigger_type: f.trigger_type.value,
    trigger_params: params,
  }});
  f.reset();
  loadTasks();
});

// === Knowledge ===
async function loadKB() {
  const s = await api('/api/knowledge/stats');
  document.getElementById('kb-stats').textContent = `Indexed: ${s.files} files, ${s.chunks} chunks`;
}
document.getElementById('kb-reindex-form').addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target;
  const paths = f.paths.value.split(',').map(s => s.trim()).filter(Boolean);
  document.getElementById('kb-stats').textContent = 'Indexing...';
  const r = await api('/api/knowledge/reindex', { method: 'POST', body: { paths, force: f.force.checked }});
  alert(r.result);
  loadKB();
});
document.getElementById('kb-search-btn').addEventListener('click', async () => {
  const q = document.getElementById('kb-search-input').value;
  if (!q) return;
  const results = await api('/api/knowledge/search?q=' + encodeURIComponent(q));
  const wrap = document.getElementById('kb-results');
  wrap.innerHTML = results.map(r => `
    <div class="card">
      <div class="meta">${escapeHTML(r.path)} #${r.chunk_index} — score ${r.score}</div>
      <pre style="white-space:pre-wrap;font-size:13px">${escapeHTML(r.content)}</pre>
    </div>
  `).join('') || '<p>No matches.</p>';
});

// === Sub-agents ===
async function loadSubagents() {
  const subs = await api('/api/subagents');
  const wrap = document.getElementById('subagents-list');
  const entries = Object.entries(subs);
  wrap.innerHTML = entries.map(([id, s]) => `
    <div class="card">
      <div><strong>${id}</strong> <span class="horizon">${s.role}</span> <span class="status-${s.status}">[${s.status}]</span></div>
      <div class="meta">${escapeHTML(s.task)}</div>
      ${s.result_preview ? `<pre style="white-space:pre-wrap;font-size:12px;margin-top:8px">${escapeHTML(s.result_preview)}</pre>` : ''}
      ${s.error ? `<div class="status-error">${escapeHTML(s.error)}</div>` : ''}
    </div>
  `).join('') || '<p>No sub-agents.</p>';
}

// === Self-mod ===
async function loadSelfMod() {
  const s = await api('/api/selfmod');
  document.getElementById('selfmod-state').innerHTML = `
    <div class="card">
      <div><strong>Prompt overlay:</strong> ${s.prompt_addition_chars} chars</div>
      ${s.prompt_addition_preview ? `<pre style="white-space:pre-wrap;font-size:13px;margin-top:8px">${escapeHTML(s.prompt_addition_preview)}</pre>` : '<div class="meta">(empty)</div>'}
      <div class="meta">Dynamic tools: ${s.dynamic_tools.join(', ') || '(none)'}</div>
    </div>
  `;
}
document.getElementById('prompt-form').addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target;
  await api('/api/selfmod/prompt', { method: 'POST', body: { addition: f.addition.value, replace: f.replace.checked }});
  f.reset();
  loadSelfMod();
});
document.getElementById('revert-btn').addEventListener('click', async () => {
  if (!confirm('Revert ALL self-modifications?')) return;
  await api('/api/selfmod/revert', { method: 'POST', body: {} });
  loadSelfMod();
});

// Refresh sub-agents periodically when tab is visible
setInterval(() => {
  if (document.querySelector('nav button.active').dataset.tab === 'subagents') loadSubagents();
}, 3000);
