/* Apex side panel — a mini chat that talks to your Apex server with the current
 * page as optional context. Uses the blocking /api/chat response (no streaming
 * needed here). */

const $ = (id) => document.getElementById(id);

async function getConfig() {
  const c = await chrome.storage.sync.get(['baseUrl', 'token']);
  return { baseUrl: (c.baseUrl || '').replace(/\/$/, ''), token: c.token || '' };
}

async function apex(path, opts = {}) {
  const { baseUrl, token } = await getConfig();
  if (!baseUrl) throw new Error('not configured');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const r = await fetch(baseUrl + path, {
    method: opts.method || 'GET',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

async function getPageContext() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return null;
    let selection = '';
    try {
      const res = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => window.getSelection().toString().slice(0, 2000),
      });
      selection = (res && res[0] && res[0].result) || '';
    } catch (_) { /* chrome:// or restricted page */ }
    return { title: tab.title || '', url: tab.url || '', selection };
  } catch (_) { return null; }
}

function addMsg(role, text, cls = '') {
  const el = document.createElement('div');
  el.className = 'ax-msg ' + role + (cls ? ' ' + cls : '');
  el.textContent = text;
  $('ax-messages').appendChild(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return el;
}

async function sendMessage(text) {
  addMsg('user', text);
  const thinking = addMsg('agent', 'thinking…', 'thinking');
  $('ax-send').disabled = true;

  let message = text;
  if ($('ax-use-page').checked) {
    const ctx = await getPageContext();
    if (ctx && ctx.url) {
      message = `[Page context]\nTitle: ${ctx.title}\nURL: ${ctx.url}` +
        (ctx.selection ? `\nSelected text: """${ctx.selection}"""` : '') +
        `\n\n[My message]\n${text}`;
    }
  }

  try {
    const res = await apex('/api/chat', { method: 'POST', body: { message } });
    thinking.classList.remove('thinking');
    thinking.textContent = res.response || '(no response)';
  } catch (e) {
    thinking.remove();
    addMsg('agent', 'Could not reach Apex: ' + e.message, 'error');
  } finally {
    $('ax-send').disabled = false;
  }
}

async function refreshStatus() {
  const status = $('ax-status');
  const cfg = await getConfig();
  if (!cfg.baseUrl) {
    $('ax-setup').hidden = false;
    $('ax-form').hidden = true;
    $('ax-context').hidden = true;
    status.textContent = 'not set up';
    return;
  }
  $('ax-setup').hidden = true;
  $('ax-form').hidden = false;
  $('ax-context').hidden = false;
  try {
    await apex('/api/status');
    status.textContent = 'connected';
    status.className = 'ax-status ok';
  } catch (e) {
    status.textContent = 'offline';
    status.className = 'ax-status err';
  }
}

// --- wire up ---
$('ax-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const text = $('ax-input').value.trim();
  if (!text) return;
  $('ax-input').value = '';
  sendMessage(text);
});
$('ax-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('ax-form').requestSubmit(); }
});
$('ax-options').addEventListener('click', () => chrome.runtime.openOptionsPage());
$('ax-open-options').addEventListener('click', () => chrome.runtime.openOptionsPage());
$('ax-send-awareness').addEventListener('click', async () => {
  const ctx = await getPageContext();
  if (!ctx || !ctx.url) return;
  try {
    await apex('/api/awareness/ingest', {
      method: 'POST',
      body: { source: 'web', content: `Viewing: ${ctx.title} — ${ctx.url}` },
    });
    $('ax-send-awareness').textContent = '✓ added';
    setTimeout(() => ($('ax-send-awareness').textContent = '＋ awareness'), 1500);
  } catch (_) {}
});

refreshStatus();
