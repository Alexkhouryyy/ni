// === Apex Agent dashboard ===

// === Token auth ===
const _TOKEN_KEY = 'apex_token';
function getToken() { return localStorage.getItem(_TOKEN_KEY) || ''; }
function setToken(t) {
  if (t) localStorage.setItem(_TOKEN_KEY, t);
  else localStorage.removeItem(_TOKEN_KEY);
}

function showLogin(msg = '') {
  const overlay = document.getElementById('login-overlay');
  if (!overlay) return;
  overlay.style.display = 'flex';
  const err = document.getElementById('login-error');
  if (err) err.textContent = msg || '';
}
function hideLogin() {
  const overlay = document.getElementById('login-overlay');
  if (overlay) overlay.style.display = 'none';
}

document.getElementById('login-form')?.addEventListener('submit', async ev => {
  ev.preventDefault();
  const t = (document.getElementById('login-token')?.value || '').trim();
  if (!t) return;
  const err = document.getElementById('login-error');
  try {
    const r = await fetch('/api/status', { headers: { 'Authorization': `Bearer ${t}` } });
    if (r.ok) {
      setToken(t);
      hideLogin();
      boot();
    } else {
      if (err) err.textContent = 'Wrong token.';
    }
  } catch (e) {
    if (err) err.textContent = 'Connection error.';
  }
});

// === API helper ===
async function api(path, opts = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const r = await fetch(path, {
    headers,
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (r.status === 401) {
    showLogin('Session expired — please re-enter your token.');
    throw new Error('Unauthorized');
  }
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
// refreshStatus and connectWS are started by boot() after auth check.

// === WebSocket live feed ===
const wsIndicator = document.getElementById('ws-indicator');
const feed = document.getElementById('event-feed');
let ws;
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const token = getToken();
  const qs = token ? `?token=${encodeURIComponent(token)}` : '';
  ws = new WebSocket(`${proto}://${location.host}/ws/live${qs}`);
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
    if (msg.type === 'chat_token') _chatAppendToken(msg.delta, msg.chat_id);
    if (msg.type === 'chat_done')  _chatFinalize(msg.chat_id, msg.response);
    if (msg.type === 'chat_error') _chatError(msg.error, msg.chat_id);
    if (msg.type === 'council_progress') _councilProgress(msg.message);
    if (msg.type === 'council_answer')   _councilAnswer(msg);
    if (msg.type === 'council_done')     _councilDone(msg);
    if (msg.type === 'council_error')    _councilError(msg.error);
  };
  setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 25000);
}
function addFeedItem(msg) {
  const div = document.createElement('div');
  div.className = 'feed-item';
  div.innerHTML = `
    <span class="ts">${fmtTs(msg.ts)}</span>
    <span class="source">${escapeHTML(msg.source || 'event')}</span>
    <span class="content">${escapeHTML(msg.content || '')}</span>`;
  feed.prepend(div);
  while (feed.children.length > 250) feed.removeChild(feed.lastChild);
  pushTicker(msg);
  spawnArc(msg.source);
  registerLiveEvent();
}
// === Tab loaders ===
async function loadTab(tab) {
  const fns = {
    overview: loadCommand,
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
    chat: loadChat,
    council: loadCouncil,
  };
  if (fns[tab]) try { await fns[tab](); } catch (e) { console.error('loadTab', tab, e); }
}

// ============== COMMAND CENTER ==============
const FEATURES = [
  { tab: 'live',        icon: '▣', label: 'Live Feed',  badge: 'events' },
  { tab: 'goals',       icon: '◇', label: 'Goals',      badge: 'goals' },
  { tab: 'memory',      icon: '◎', label: 'Memory',     badge: 'memories' },
  { tab: 'graph',       icon: '◈', label: 'Knowledge',  badge: 'entities' },
  { tab: 'reflections', icon: '⌘', label: 'Reflect',    badge: 'reflections' },
  { tab: 'telemetry',   icon: '▤', label: 'Telemetry' },
  { tab: 'replay',      icon: '▷', label: 'Replay' },
  { tab: 'schedule',    icon: '◷', label: 'Schedule',   badge: 'tasks' },
  { tab: 'subagents',   icon: '⌥', label: 'Sub-agents', badge: 'subagents' },
  { tab: 'knowledge',   icon: '≡', label: 'Knwl Base' },
  { tab: 'selfmod',     icon: '✎', label: 'Self-Mod' },
  { tab: 'phone',       icon: '☎', label: 'Phone' },
];

// World hub coordinates [lat, lng] — agent activity lights these up
const HUBS = [
  [37.77, -122.42], [40.71, -74.0], [51.50, -0.12], [35.68, 139.69],
  [1.35, 103.82], [-33.87, 151.21], [52.52, 13.40], [19.08, 72.88],
  [-23.55, -46.63], [55.75, 37.62], [48.85, 2.35], [25.20, 55.27],
];
const SRC_COLOR = {
  stt: '#5fd8ff', tool: '#8a7cff', awareness: '#3ddc97', error: '#ff6a6a',
  proactive: '#ffb547', event: '#5fd8ff', agent: '#8a7cff',
};

let globeInstance = null;
let globeArcs = [];
let commandInited = false;

// Solar system body definitions
const SOLAR_BODIES = {
  sun:     { label:'Sun',     icon:'☀',  colors:['#ffee00','#ff8800','#ff5500'],           atm:'#ff9900', atmAlt:0.55, speed:0.25 },
  mercury: { label:'Mercury', icon:'☿',  colors:['#9e9e9e','#777777','#6d6d6d'],           atm:'#888888', atmAlt:0.04, speed:0.10 },
  venus:   { label:'Venus',   icon:'♀',  colors:['#e8c887','#d4a84b','#c4933e'],           atm:'#dd9900', atmAlt:0.38, speed:0.06 },
  earth:   { label:'Earth',   icon:'⊕',
             texture:'//unpkg.com/three-globe/example/img/earth-night.jpg',
             bumpTexture:'//unpkg.com/three-globe/example/img/earth-topology.png',
             atm:'#5fd8ff', atmAlt:0.21, speed:0.70 },
  moon:    { label:'Moon',    icon:'☽',  colors:['#d4d0c8','#b8b4ac','#a09890'],           atm:'#bbbbcc', atmAlt:0.02, speed:0.05 },
  mars:    { label:'Mars',    icon:'♂',  colors:['#c1440e','#a03010','#8b2500'],           atm:'#ff5522', atmAlt:0.10, speed:0.65 },
  jupiter: { label:'Jupiter', icon:'♃',  colors:['#c88b3a','#e0b060','#a06020','#d09050','#c88b3a'], bands:true,
             atm:'#ddaa55', atmAlt:0.16, speed:1.30 },
  saturn:  { label:'Saturn',  icon:'♄',  colors:['#e4d191','#d4b860','#c9a045'],           atm:'#ddcc60', atmAlt:0.14, speed:1.10 },
  uranus:  { label:'Uranus',  icon:'♅',  colors:['#7de8e8','#60d0d0','#4db8b8'],           atm:'#88ffff', atmAlt:0.22, speed:0.90 },
  neptune: { label:'Neptune', icon:'♆',  colors:['#3b5bdb','#2a4bc8','#1a3a9e'],           atm:'#5588ff', atmAlt:0.24, speed:0.95 },
  pluto:   { label:'Pluto',   icon:'✦',  colors:['#b8a898','#a09080','#8a7868'],           atm:'#998888', atmAlt:0.03, speed:0.03 },
};
let currentBody = 'earth';
const _bodyTextureCache = {};

function makeBodyTexture(body) {
  const w = 512, h = 256;
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (body.bands) {
    const bh = h / body.colors.length;
    body.colors.forEach((col, i) => {
      ctx.fillStyle = col;
      ctx.fillRect(0, Math.floor(i * bh), w, Math.ceil(bh) + 1);
    });
  } else {
    const g = ctx.createLinearGradient(0, 0, w, h);
    body.colors.forEach((col, i) => g.addColorStop(i / (body.colors.length - 1), col));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  }
  return canvas.toDataURL('image/jpeg', 0.9);
}

function switchBody(key) {
  const body = SOLAR_BODIES[key];
  if (!body || !globeInstance) return;
  currentBody = key;
  document.querySelectorAll('.planet-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.body === key));
  let tex = body.texture;
  if (!tex) {
    if (!_bodyTextureCache[key]) _bodyTextureCache[key] = makeBodyTexture(body);
    tex = _bodyTextureCache[key];
  }
  globeInstance
    .globeImageUrl(tex)
    .bumpImageUrl(body.bumpTexture || '')
    .atmosphereColor(body.atm)
    .atmosphereAltitude(body.atmAlt);
  globeInstance.controls().autoRotateSpeed = body.speed;
  const glow = document.querySelector('.globe-glow');
  if (glow) {
    const c = body.atm;
    glow.style.background =
      `radial-gradient(circle, ${c}2e 0%, ${c}0d 55%, transparent 72%)`;
  }
}

function renderPlanetSelector() {
  const sel = document.getElementById('planet-selector');
  if (!sel || sel.dataset.inited) return;
  sel.dataset.inited = '1';
  sel.innerHTML = Object.entries(SOLAR_BODIES).map(([key, body]) =>
    `<button class="planet-btn${key === currentBody ? ' active' : ''}" data-body="${key}" title="${body.label}">` +
    `<span class="planet-btn-icon">${body.icon}</span>` +
    `<span class="planet-btn-label">${body.label}</span></button>`
  ).join('');
  sel.addEventListener('click', e => {
    const btn = e.target.closest('.planet-btn');
    if (btn) switchBody(btn.dataset.body);
  });
}
let liveEventTimes = [];

function registerLiveEvent() { liveEventTimes.push(Date.now()); }
function refreshEventBadge() {
  const cutoff = Date.now() - 300000;
  liveEventTimes = liveEventTimes.filter(t => t > cutoff);
  setBadge('events', liveEventTimes.length);
}
setInterval(refreshEventBadge, 15000);

function setBadge(key, val) {
  const el = document.getElementById('badge-' + key);
  if (!el) return;
  if (val && val > 0) { el.textContent = val > 99 ? '99+' : val; el.style.display = 'flex'; }
  else el.style.display = 'none';
}

function buildFeatureOrbit() {
  const orbit = document.getElementById('feature-orbit');
  if (!orbit || orbit.childElementCount) return;
  const R = 318;
  FEATURES.forEach((f, i) => {
    const ang = (-90 + i * (360 / FEATURES.length)) * Math.PI / 180;
    const node = document.createElement('div');
    node.className = 'feat-node';
    node.style.left = (R * Math.cos(ang)) + 'px';
    node.style.top = (R * Math.sin(ang)) + 'px';
    node.style.animationDelay = (i * 0.35) + 's';
    node.title = f.label;
    node.innerHTML = `
      <span class="feat-node-icon">${f.icon}</span>
      <span class="feat-node-label">${f.label}</span>
      ${f.badge ? `<span class="feat-node-badge" id="badge-${f.badge}" style="display:none">0</span>` : ''}`;
    node.addEventListener('click', () => {
      document.querySelector(`.nav-btn[data-tab="${f.tab}"]`)?.click();
    });
    orbit.appendChild(node);
  });
}

function initStarfield() {
  const cv = document.getElementById('cmd-starfield');
  if (!cv) return;
  const ctx = cv.getContext('2d');
  let stars = [];
  function resize() {
    cv.width = cv.offsetWidth; cv.height = cv.offsetHeight;
    const n = Math.floor(cv.width * cv.height / 7000);
    stars = Array.from({ length: n }, () => ({
      x: Math.random() * cv.width, y: Math.random() * cv.height,
      r: Math.random() * 1.4 + 0.2,
      tw: Math.random() * Math.PI * 2,
      sp: Math.random() * 0.018 + 0.003,
    }));
  }
  resize();
  window.addEventListener('resize', resize);
  (function draw() {
    ctx.clearRect(0, 0, cv.width, cv.height);
    for (const s of stars) {
      s.tw += s.sp;
      const a = 0.3 + Math.sin(s.tw) * 0.35;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(170,210,255,${Math.max(0, a)})`;
      ctx.fill();
    }
    requestAnimationFrame(draw);
  })();
}

function initGlobe() {
  const mount = document.getElementById('globe');
  if (!mount || globeInstance) return;
  if (typeof Globe === 'undefined') {
    mount.innerHTML = '<div class="globe-fallback"></div>';
    return;
  }
  try {
    globeInstance = Globe()(mount)
      .width(460).height(460)
      .backgroundColor('rgba(0,0,0,0)')
      .globeImageUrl('//unpkg.com/three-globe/example/img/earth-night.jpg')
      .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
      .showAtmosphere(true)
      .atmosphereColor('#5fd8ff')
      .atmosphereAltitude(0.21)
      .arcsData(globeArcs)
      .arcColor('color')
      .arcAltitude('alt')
      .arcStroke(0.55)
      .arcDashLength(0.45)
      .arcDashGap(0.25)
      .arcDashAnimateTime(1600)
      .ringsData(HUBS.slice(0, 4).map(([lat, lng]) => ({ lat, lng })))
      .ringColor(() => (t => `rgba(95,216,255,${1 - t})`))
      .ringMaxRadius(4)
      .ringPropagationSpeed(1.6)
      .ringRepeatPeriod(1400);
    const ctrl = globeInstance.controls();
    ctrl.autoRotate = true;
    ctrl.autoRotateSpeed = 0.7;
    ctrl.enableZoom = false;
  } catch (e) {
    console.error('globe init failed', e);
    mount.innerHTML = '<div class="globe-fallback"></div>';
  }
}

function spawnArc(source) {
  if (!globeInstance) return;
  const a = HUBS[Math.floor(Math.random() * HUBS.length)];
  let b = HUBS[Math.floor(Math.random() * HUBS.length)];
  if (a === b) b = HUBS[(HUBS.indexOf(b) + 1) % HUBS.length];
  const color = SRC_COLOR[source] || '#5fd8ff';
  const arc = {
    startLat: a[0], startLng: a[1], endLat: b[0], endLng: b[1],
    color: [color, color], alt: 0.18 + Math.random() * 0.22,
  };
  globeArcs = [...globeArcs, arc].slice(-14);
  globeInstance.arcsData(globeArcs);
  setTimeout(() => {
    globeArcs = globeArcs.filter(x => x !== arc);
    if (globeInstance) globeInstance.arcsData(globeArcs);
  }, 4200);
}

// Ambient arcs keep the globe alive even when the agent is idle
setInterval(() => {
  if (globeInstance && document.getElementById('tab-overview')?.classList.contains('active')) {
    spawnArc('event');
  }
}, 3600);

function pushTicker(msg) {
  const track = document.getElementById('cmd-ticker');
  if (!track) return;
  track.querySelector('.cmd-ticker-idle')?.remove();
  const item = document.createElement('div');
  item.className = 'cmd-ticker-item';
  const txt = (msg.content || '').slice(0, 70);
  item.innerHTML = `<span class="tk-src">${escapeHTML(msg.source || 'event')}</span>${escapeHTML(txt)}`;
  track.prepend(item);
  while (track.children.length > 7) track.removeChild(track.lastChild);
}

function startCmdClock() {
  const el = document.getElementById('cmd-clock');
  if (!el) return;
  const tick = () => { el.textContent = new Date().toLocaleTimeString([], { hour12: false }); };
  tick();
  setInterval(tick, 1000);
}

async function loadCommand() {
  if (!commandInited) {
    commandInited = true;
    buildFeatureOrbit();
    initStarfield();
    initGlobe();
    renderPlanetSelector();
    startCmdClock();
  }
  try {
    const [tel, goals, mems, tasks, refl, ents, subs, status] = await Promise.all([
      api('/api/telemetry?days=7'),
      api('/api/goals?active_only=true'),
      api('/api/memories?limit=500'),
      api('/api/tasks'),
      api('/api/reflections?status=pending'),
      api('/api/entities?limit=500'),
      api('/api/subagents'),
      api('/api/status').catch(() => ({})),
    ]);
    document.getElementById('hud-cost').textContent = fmtCost(tel.total_cost_usd);
    document.getElementById('hud-cost-meta').textContent =
      fmtNum((tel.total_input_tokens || 0) + (tel.total_output_tokens || 0)) + ' tokens';
    const cache = (tel.cache_hit_rate || 0) * 100;
    document.getElementById('hud-cache').textContent = cache.toFixed(1) + '%';
    document.getElementById('hud-cache-bar').style.width = cache + '%';
    document.getElementById('hud-calls').textContent = fmtNum(tel.total_calls);
    document.getElementById('hud-calls-meta').textContent =
      (tel.by_model || []).length + ' models active';
    document.getElementById('hud-model').textContent =
      (status.model || '—').replace('claude-', '');
    document.getElementById('hud-systems').textContent =
      `${status.tools_count || 0} tools · ${status.awareness_enabled ? 'aware' : 'idle'}`;

    const entCount = (ents.nodes || ents || []).length || 0;
    const runningSubs = Object.values(subs || {}).filter(s => s.status === 'running').length;
    setBadge('goals', goals.length);
    setBadge('memories', mems.length);
    setBadge('entities', entCount);
    setBadge('reflections', refl.length);
    setBadge('tasks', tasks.length);
    setBadge('subagents', runningSubs);
  } catch (e) { console.error('command', e); }
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

// Refresh command center every 20s
setInterval(() => {
  if (document.querySelector('.nav-btn.active')?.dataset.tab === 'overview') loadCommand();
}, 20000);

// ============== CHAT ==============
let activeChatId = null;
let currentAgentBubble = null;
let currentAgentText = '';

function loadChat() {
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send');
  loadModelPicker();
  if (input._chatWired) return;
  input._chatWired = true;
  sendBtn.addEventListener('click', sendChat);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 200) + 'px';
  });
  document.getElementById('chat-mic')?.addEventListener('click', toggleMic);
  document.getElementById('chat-council')?.addEventListener('click', () => {
    const text = input.value.trim();
    if (!text) { input.focus(); return; }
    document.querySelector('.nav-btn[data-tab="council"]')?.click();
    const q = document.getElementById('council-question');
    if (q) q.value = text;
    runCouncil();
  });
}

// ============== MODEL PICKER ==============
async function loadModelPicker() {
  const sel = document.getElementById('chat-model');
  if (!sel || sel._wired) {
    if (sel) refreshModelSelection();
    return;
  }
  sel._wired = true;
  try {
    const data = await api('/api/models');
    sel.innerHTML = '';
    data.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.model;
      opt.textContent = m.available ? m.model : `${m.model} (no API key)`;
      opt.disabled = !m.available;
      sel.appendChild(opt);
    });
    sel.value = data.current;
  } catch (e) { console.error('loadModelPicker', e); }
  sel.addEventListener('change', async () => {
    const msg = document.getElementById('chat-model-msg');
    try {
      const r = await api('/api/model', { method: 'POST', body: { model: sel.value } });
      if (msg) { msg.textContent = r.message; msg.className = 'chat-model-msg ' + (r.ok ? 'ok' : 'err'); }
      refreshStatus();
    } catch (e) {
      if (msg) { msg.textContent = 'Switch failed: ' + e.message; msg.className = 'chat-model-msg err'; }
    }
  });
}
async function refreshModelSelection() {
  const sel = document.getElementById('chat-model');
  if (!sel) return;
  try { sel.value = (await api('/api/models')).current; } catch (e) {}
}

function _appendChatMsg(role, text) {
  const msgs = document.getElementById('chat-messages');
  if (!msgs) return null;
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.innerHTML = `<div class="chat-msg-role">${role === 'user' ? 'You' : 'Agent'}</div>` +
                  `<div class="chat-msg-content">${escapeHTML(text)}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send');
  const text = (input?.value || '').trim();
  if (!text || activeChatId) return;

  input.value = '';
  input.style.height = 'auto';
  _appendChatMsg('user', text);

  currentAgentText = '';
  currentAgentBubble = _appendChatMsg('agent', '');
  currentAgentBubble.classList.add('streaming');
  sendBtn.disabled = true;

  // Generate chat_id client-side so WS tokens are routed before POST returns
  const chatId = Math.random().toString(36).slice(2, 10);
  activeChatId = chatId;

  try {
    await api('/api/chat', { method: 'POST', body: { message: text, chat_id: chatId } });
  } catch (e) {
    if (activeChatId === chatId) _chatError(`HTTP error: ${e.message}`, chatId);
    return;
  }
  // Fallback: finalize if chat_done already arrived via WS and cleared activeChatId
  if (activeChatId === chatId) _chatFinalize(chatId);
}

function _chatAppendToken(delta, chatId) {
  if (activeChatId !== chatId || !currentAgentBubble) return;
  currentAgentText += delta;
  const el = currentAgentBubble.querySelector('.chat-msg-content');
  if (el) el.textContent = currentAgentText;
  const msgs = document.getElementById('chat-messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function _chatFinalize(chatId, response) {
  if (activeChatId !== chatId) return;
  if (currentAgentBubble) currentAgentBubble.classList.remove('streaming');
  const spoken = response || currentAgentText;
  currentAgentBubble = null;
  activeChatId = null;
  const sendBtn = document.getElementById('chat-send');
  if (sendBtn) sendBtn.disabled = false;
  if (spoken) speakText(spoken);
}

function _chatError(error, chatId) {
  if (activeChatId !== chatId) return;
  if (currentAgentBubble) {
    const el = currentAgentBubble.querySelector('.chat-msg-content');
    if (el) { el.textContent = error; el.classList.add('chat-error-text'); }
    currentAgentBubble.classList.remove('streaming');
    currentAgentBubble = null;
  }
  activeChatId = null;
  const sendBtn = document.getElementById('chat-send');
  if (sendBtn) sendBtn.disabled = false;
}

// ============== VOICE ==============
let mediaRecorder = null;
let audioChunks = [];

async function toggleMic() {
  const micBtn = document.getElementById('chat-mic');
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    alert('Microphone unavailable or permission denied.');
    return;
  }
  audioChunks = [];
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = e => { if (e.data.size) audioChunks.push(e.data); };
  mediaRecorder.onstop = async () => {
    stream.getTracks().forEach(t => t.stop());
    micBtn?.classList.remove('recording');
    const type = mediaRecorder.mimeType || 'audio/webm';
    await transcribeAndSend(new Blob(audioChunks, { type }), type);
  };
  mediaRecorder.start();
  micBtn?.classList.add('recording');
}

async function transcribeAndSend(blob, type) {
  const micBtn = document.getElementById('chat-mic');
  const input = document.getElementById('chat-input');
  micBtn?.classList.add('transcribing');
  const ext = (type.includes('mp4') || type.includes('mpeg') || type.includes('m4a')) ? 'mp4' : 'webm';
  const fd = new FormData();
  fd.append('file', blob, 'speech.' + ext);
  try {
    const r = await fetch('/api/transcribe', { method: 'POST', body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'transcription failed');
    if (data.text) {
      input.value = data.text;
      sendChat();
    }
  } catch (e) {
    alert('Voice input failed: ' + e.message);
  } finally {
    micBtn?.classList.remove('transcribing');
  }
}

function speakText(text) {
  if (!document.getElementById('voice-output')?.checked) return;
  const engine = document.getElementById('voice-engine')?.value || 'browser';
  if (engine === 'openai') speakOpenAI(text);
  else speakBrowser(text);
}
function speakBrowser(text) {
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.05;
    window.speechSynthesis.speak(u);
  } catch (e) {}
}
async function speakOpenAI(text) {
  try {
    const r = await fetch('/api/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!r.ok) { speakBrowser(text); return; }
    const audio = new Audio(URL.createObjectURL(await r.blob()));
    audio.play().catch(() => {});
  } catch (e) { speakBrowser(text); }
}

// ============== COUNCIL ==============
let councilRunning = false;

async function loadCouncil() {
  const form = document.getElementById('council-form');
  if (!form || form._wired) return;
  form._wired = true;
  form.addEventListener('submit', e => { e.preventDefault(); runCouncil(); });
  try {
    const data = await api('/api/council/roster');
    const panel = document.getElementById('council-panel');
    if (panel) {
      panel.innerHTML = (data.roster || []).map(m =>
        `<label class="council-pick${m.available ? '' : ' disabled'}">` +
        `<input type="checkbox" value="${escapeHTML(m.model)}" ${m.available ? 'checked' : 'disabled'}>` +
        `<span>${escapeHTML(m.label)}${m.available ? '' : ' · no API key'}</span></label>`
      ).join('');
    }
    const preset = document.getElementById('council-preset');
    if (preset) {
      preset.innerHTML = (data.presets || []).map(p =>
        `<option value="${escapeHTML(p.id)}">${escapeHTML(p.label)}</option>`).join('');
    }
  } catch (e) { /* roster fetch failed — council still works with backend defaults */ }
}

async function runCouncil() {
  if (councilRunning) return;
  const q = document.getElementById('council-question').value.trim();
  if (!q) return;
  const rounds = parseInt(document.getElementById('council-rounds').value, 10);
  const presetEl = document.getElementById('council-preset');
  const preset = presetEl ? presetEl.value : 'general';
  const picks = Array.from(document.querySelectorAll('#council-panel input'));
  const panel = picks.filter(c => c.checked).map(c => c.value);
  if (picks.length && panel.length < 2) {
    _councilError('Pick at least 2 members for the council.');
    return;
  }
  const btn = document.getElementById('council-convene');
  const progress = document.getElementById('council-progress');
  const verdict = document.getElementById('council-verdict');
  const transcript = document.getElementById('council-transcript');

  councilRunning = true;
  btn.disabled = true;
  btn.textContent = 'Council in session…';
  verdict.innerHTML = '';
  transcript.innerHTML = '';
  progress.innerHTML = '<div class="council-step">Convening the council…</div>';

  const body = { question: q, rounds, preset };
  if (panel.length) body.panel = panel;
  try {
    const result = await api('/api/council', { method: 'POST', body });
    if (councilRunning) _councilDone(result);  // fallback if the WS event didn't arrive
  } catch (e) {
    _councilError('Request failed: ' + e.message);
  }
}

function _councilProgress(msg) {
  const progress = document.getElementById('council-progress');
  if (progress) {
    const d = document.createElement('div');
    d.className = 'council-step';
    d.textContent = msg;
    progress.appendChild(d);
  }
}

function _councilRoundGroup(r) {
  const transcript = document.getElementById('council-transcript');
  if (!transcript) return null;
  let group = transcript.querySelector(`.council-round[data-round="${r}"]`);
  if (!group) {
    group = document.createElement('div');
    group.className = 'council-round';
    group.dataset.round = r;
    const label = document.createElement('div');
    label.className = 'council-round-label';
    label.textContent = r === 0 ? 'Opening statements' : `Debate round ${r}`;
    const cards = document.createElement('div');
    cards.className = 'cards';
    group.appendChild(label);
    group.appendChild(cards);
    transcript.appendChild(group);
  }
  return group;
}

function _councilAnswer(data) {
  const group = _councilRoundGroup(data.round);
  if (!group) return;
  const entry = document.createElement('div');
  entry.className = 'council-entry';
  entry.innerHTML =
    `<div class="council-entry-head">${escapeHTML(data.label)}</div>` +
    `<div class="council-entry-body">${escapeHTML(data.text)}</div>`;
  group.querySelector('.cards').appendChild(entry);
}

function _councilDone(data) {
  if (!councilRunning) return;  // already rendered (WS + POST both fired)
  councilRunning = false;
  const btn = document.getElementById('council-convene');
  if (btn) { btn.disabled = false; btn.textContent = 'Convene council'; }
  const verdict = document.getElementById('council-verdict');
  const transcript = document.getElementById('council-transcript');

  if (verdict) {
    verdict.innerHTML =
      `<div class="council-verdict-head">Verdict <span class="council-members">${(data.members || []).join(' · ')}</span></div>` +
      `<div class="council-verdict-body">${escapeHTML(data.final_answer || '')}</div>`;
  }
  // Transcript is normally built live from council_answer events. Only rebuild
  // it here if those events never arrived (POST-only fallback).
  if (transcript && !transcript.children.length) {
    (data.transcript || []).forEach(e => _councilAnswer(e));
  }
}

function _councilError(err) {
  councilRunning = false;
  const btn = document.getElementById('council-convene');
  if (btn) { btn.disabled = false; btn.textContent = 'Convene council'; }
  const progress = document.getElementById('council-progress');
  if (progress) {
    const d = document.createElement('div');
    d.className = 'council-step council-step-err';
    d.textContent = 'Council failed: ' + err;
    progress.appendChild(d);
  }
}

// === Boot — probe auth before starting the app ===
let _booted = false;
async function boot() {
  if (_booted) return;
  const token = getToken();
  try {
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
    const r = await fetch('/api/status', { headers });
    if (r.status === 401) {
      if (token) setToken('');  // stored token is no longer valid
      showLogin(token ? 'Token invalid or changed — please re-enter.' : '');
      return;
    }
  } catch (_) { /* network error — proceed anyway */ }
  _booted = true;
  hideLogin();
  refreshStatus();
  setInterval(refreshStatus, 5000);
  connectWS();
  loadTab('overview');
}
boot();
