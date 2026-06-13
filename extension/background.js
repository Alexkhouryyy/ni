/* Apex extension background service worker.
 * Opens the side panel from the toolbar icon or the Ctrl+Shift+A command. */

chrome.runtime.onInstalled.addListener(() => {
  // Clicking the toolbar icon opens the side panel directly.
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  }
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== 'open-apex') return;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) await chrome.sidePanel.open({ tabId: tab.id });
  } catch (e) {
    // Fallback for browsers that only allow window-level open
    try {
      const win = await chrome.windows.getCurrent();
      await chrome.sidePanel.open({ windowId: win.id });
    } catch (_) {}
  }
});

// Some Chrome builds need an explicit onClicked handler as well.
if (chrome.action && chrome.action.onClicked) {
  chrome.action.onClicked.addListener(async (tab) => {
    try { await chrome.sidePanel.open({ tabId: tab.id }); } catch (_) {}
  });
}
