// WebRAG Background Service Worker (Manifest V3)

// Configure side panel to open on action click immediately
if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((err) => {
    console.warn('[WebRAG] setPanelBehavior error:', err);
  });
}

chrome.runtime.onInstalled.addListener(() => {
  console.log('[WebRAG] Extension installed');

  // Configure side panel to open on action click
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((err) => {
      console.warn('[WebRAG] Failed to setPanelBehavior:', err);
    });
  }
});

// Fallback for action click to ensure side panel opens
chrome.action.onClicked.addListener(async (tab) => {
  if (tab.windowId && chrome.sidePanel && chrome.sidePanel.open) {
    try {
      await chrome.sidePanel.open({ windowId: tab.windowId });
    } catch (err) {
      console.warn('[WebRAG] Failed to open side panel on click:', err);
    }
  }
});

// Message listener for coordinating between content script and side panel
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'PING') {
    sendResponse({ status: 'ok' });
  }
  return true;
});
