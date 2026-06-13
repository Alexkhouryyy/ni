/* Apex mobile layer — bottom tab-bar, drawer nav, and a talk FAB.
 *
 * Voice reuses the existing desktop chat pipeline (toggleMic → /api/transcribe →
 * sendChat, and speakText for replies) so we get server-side Whisper accuracy
 * instead of the patchier browser SpeechRecognition API. This file only adds the
 * mobile chrome and wires the floating mic button to that proven flow.
 */
(function () {
  function $(id) { return document.getElementById(id); }

  function init() {
    const body = document.body;
    const openDrawer = () => body.classList.add('drawer-open');
    const closeDrawer = () => body.classList.remove('drawer-open');

    // Hamburger + backdrop
    document.addEventListener('click', (e) => {
      if (e.target.closest('#mt-burger')) openDrawer();
      else if (e.target.id === 'drawer-backdrop') closeDrawer();
    });

    function syncTabbar(tab) {
      document.querySelectorAll('#mobile-tabbar [data-mtab]').forEach((b) =>
        b.classList.toggle('active', b.dataset.mtab === tab));
    }
    function activateTab(tab) {
      const navBtn = document.querySelector(`.nav-btn[data-tab="${tab}"]`);
      if (navBtn) navBtn.click();
      syncTabbar(tab);
      closeDrawer();
    }

    // Bottom tab bar → delegate to the real sidebar nav buttons
    document.querySelectorAll('#mobile-tabbar [data-mtab]').forEach((b) => {
      if (b.dataset.mtab === 'more') { b.addEventListener('click', openDrawer); return; }
      b.addEventListener('click', () => activateTab(b.dataset.mtab));
    });
    // Keep the tab bar + drawer in sync when the sidebar is used directly
    document.querySelectorAll('#sidebar .nav-btn').forEach((b) =>
      b.addEventListener('click', () => { syncTabbar(b.dataset.tab); closeDrawer(); }));

    // Mirror the live/offline indicator into the mobile top bar
    const wsInd = $('ws-indicator');
    const mtLive = document.querySelector('#mobile-topbar .mt-live');
    if (wsInd && mtLive) {
      const reflect = () => {
        const on = wsInd.classList.contains('ws-on');
        mtLive.textContent = on ? '● live' : '● offline';
        mtLive.classList.toggle('ws-on', on);
      };
      new MutationObserver(reflect).observe(wsInd, {
        attributes: true, childList: true, characterData: true, subtree: true,
      });
      reflect();
    }

    // Talk FAB → reuse the existing chat recorder + TTS
    const fab = $('mobile-talk');
    if (fab) {
      fab.addEventListener('click', () => {
        activateTab('chat');
        const vo = $('voice-output');
        if (vo && !vo.checked) vo.checked = true; // ensure replies are spoken
        if (typeof window.toggleMic === 'function') window.toggleMic();
      });
      const micBtn = $('chat-mic');
      const status = $('mobile-voice-status');
      if (micBtn) {
        const reflect = () => {
          const recording = micBtn.classList.contains('recording');
          const transcribing = micBtn.classList.contains('transcribing');
          fab.classList.toggle('listening', recording);
          if (status) {
            if (transcribing) { status.textContent = 'Transcribing…'; status.classList.add('show'); }
            else if (recording) { status.textContent = 'Listening… tap to stop'; status.classList.add('show'); }
            else { status.classList.remove('show'); }
          }
        };
        new MutationObserver(reflect).observe(micBtn, { attributes: true, attributeFilter: ['class'] });
      }
    }

    // Deep links from manifest shortcuts: ?tab=chat&talk=1
    try {
      const p = new URLSearchParams(location.search);
      const tab = p.get('tab');
      if (tab) setTimeout(() => activateTab(tab), 300);
      if (p.get('talk') === '1') setTimeout(() => fab && fab.click(), 800);
    } catch (_e) { /* ignore */ }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
