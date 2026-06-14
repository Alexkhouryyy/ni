const $ = (id) => document.getElementById(id);

// Restore saved config
chrome.storage.sync.get(['baseUrl', 'token']).then((c) => {
  $('baseUrl').value = c.baseUrl || '';
  $('token').value = c.token || '';
});

// Paste a pairing link → split into base URL + token.
// Format: <base>/?source=pair#token=XYZ
$('pair').addEventListener('input', () => {
  const v = $('pair').value.trim();
  if (!v) return;
  try {
    const u = new URL(v);
    const hash = new URLSearchParams((u.hash || '').replace(/^#/, ''));
    const token = hash.get('token') || '';
    $('baseUrl').value = `${u.protocol}//${u.host}`;
    if (token) $('token').value = token;
  } catch (_) { /* not a full URL yet */ }
});

$('save').addEventListener('click', async () => {
  const baseUrl = $('baseUrl').value.trim().replace(/\/$/, '');
  const token = $('token').value.trim();
  await chrome.storage.sync.set({ baseUrl, token });
  const ok = $('saved');
  ok.hidden = false;
  setTimeout(() => (ok.hidden = true), 1500);
});
