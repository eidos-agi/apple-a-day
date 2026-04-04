// apple-a-day browser monitor — background service worker
// Captures tab lifecycle events, periodic snapshots, and badge updates.

const NATIVE_HOST = "com.eidos.aad.browser";
const SNAPSHOT_ALARM = "aad-snapshot";
const SNAPSHOT_INTERVAL_MIN = 5;
const MAX_BUFFER_SIZE = 1000;

// --- Instance identity (salted GUID, generated once per install) ---

let instanceId = null;

async function getInstanceId() {
  if (instanceId) return instanceId;
  const data = await chrome.storage.local.get("instanceId");
  if (data.instanceId) {
    instanceId = data.instanceId;
    return instanceId;
  }
  instanceId = await generateInstanceId();
  await chrome.storage.local.set({ instanceId });
  return instanceId;
}

async function generateInstanceId() {
  const salt = crypto.getRandomValues(new Uint8Array(16)).join("");
  const raw = [
    crypto.randomUUID(),
    navigator.userAgent,
    navigator.language,
    screen.width + "x" + screen.height,
    Date.now().toString(36),
    salt,
  ].join("|");
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(raw));
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// --- Tab creation time tracking ---

const tabCreatedAt = new Map();

async function loadTabTimes() {
  const data = await chrome.storage.local.get("tabCreatedAt");
  if (data.tabCreatedAt) {
    for (const [id, ts] of Object.entries(data.tabCreatedAt)) {
      tabCreatedAt.set(Number(id), ts);
    }
  }
}

async function persistTabTimes() {
  const obj = {};
  for (const [id, ts] of tabCreatedAt) {
    obj[id] = ts;
  }
  await chrome.storage.local.set({ tabCreatedAt: obj });
}

// --- Event logging ---

function nowISO() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "");
}

async function logEvent(event) {
  event.ts = nowISO();
  event.instance_id = await getInstanceId();
  // Buffer locally
  await bufferEvent(event);
  // Try native messaging
  sendToNativeHost(event);
}

async function bufferEvent(event) {
  const data = await chrome.storage.local.get("events");
  const events = data.events || [];
  events.push(event);
  // Ring buffer: keep last MAX_BUFFER_SIZE
  if (events.length > MAX_BUFFER_SIZE) {
    events.splice(0, events.length - MAX_BUFFER_SIZE);
  }
  await chrome.storage.local.set({ events });
}

function sendToNativeHost(message) {
  try {
    chrome.runtime.sendNativeMessage(NATIVE_HOST, message, (response) => {
      if (chrome.runtime.lastError) {
        // Native host not installed — that's fine, events are buffered locally
        console.debug("aad: native host unavailable:", chrome.runtime.lastError.message);
      }
    });
  } catch {
    // Extension context invalidated or similar — ignore
  }
}

// --- Badge ---

async function updateBadge() {
  const tabs = await chrome.tabs.query({});
  const count = tabs.length;
  chrome.action.setBadgeText({ text: String(count) });
  chrome.action.setBadgeBackgroundColor({
    color: count > 50 ? "#e74c3c" : count > 25 ? "#f39c12" : "#27ae60",
  });
}

// --- Tab event listeners ---

chrome.tabs.onCreated.addListener(async (tab) => {
  tabCreatedAt.set(tab.id, nowISO());
  await persistTabTimes();
  await logEvent({
    type: "tab_event",
    event: "open",
    tab_id: tab.id,
    window_id: tab.windowId,
    url: tab.pendingUrl || tab.url || "",
    title: tab.title || "",
  });
  await updateBadge();
});

chrome.tabs.onRemoved.addListener(async (tabId, removeInfo) => {
  tabCreatedAt.delete(tabId);
  await persistTabTimes();
  await logEvent({
    type: "tab_event",
    event: "close",
    tab_id: tabId,
    window_id: removeInfo.windowId,
  });
  await updateBadge();
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // Only log URL changes (navigations), not every title/favicon update
  if (!changeInfo.url) return;
  await logEvent({
    type: "tab_event",
    event: "navigate",
    tab_id: tabId,
    window_id: tab.windowId,
    url: changeInfo.url,
    title: tab.title || "",
  });
});

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  const tab = await chrome.tabs.get(activeInfo.tabId);
  await logEvent({
    type: "tab_event",
    event: "focus",
    tab_id: activeInfo.tabId,
    window_id: activeInfo.windowId,
    url: tab.url || "",
    title: tab.title || "",
  });
});

// --- Snapshot alarm ---

chrome.alarms.create(SNAPSHOT_ALARM, { periodInMinutes: SNAPSHOT_INTERVAL_MIN });

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== SNAPSHOT_ALARM) return;
  await takeSnapshot();
});

async function takeSnapshot() {
  const tabs = await chrome.tabs.query({});
  const windows = await chrome.windows.getAll();
  const now = nowISO();

  const snapshot = {
    type: "snapshot",
    ts: now,
    tab_count: tabs.length,
    window_count: windows.length,
    tabs: tabs.map((t) => {
      const created = tabCreatedAt.get(t.id);
      const ageMin = created
        ? Math.round((Date.now() - new Date(created).getTime()) / 60000)
        : null;
      return {
        id: t.id,
        window_id: t.windowId,
        url: t.url || "",
        title: t.title || "",
        active: t.active,
        age_min: ageMin,
      };
    }),
  };

  await bufferEvent(snapshot);
  sendToNativeHost(snapshot);
  await updateBadge();
}

// --- Initialization ---

chrome.runtime.onInstalled.addListener(async () => {
  await loadTabTimes();
  // Seed creation times for all currently open tabs
  const tabs = await chrome.tabs.query({});
  const now = nowISO();
  for (const tab of tabs) {
    if (!tabCreatedAt.has(tab.id)) {
      tabCreatedAt.set(tab.id, now);
    }
  }
  await persistTabTimes();
  await updateBadge();
  // Take initial snapshot
  await takeSnapshot();
});

// Handle messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "snapshot") {
    takeSnapshot();
  }
});

// Also load on service worker startup (not just install)
loadTabTimes().then(updateBadge);
