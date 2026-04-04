// apple-a-day browser monitor — popup logic

async function render() {
  // Live tab/window count
  const tabs = await chrome.tabs.query({});
  const windows = await chrome.windows.getAll();
  document.getElementById("tab-count").textContent = tabs.length;
  document.getElementById("window-count").textContent = windows.length;

  // Tabs opened today
  const data = await chrome.storage.local.get("events");
  const events = data.events || [];
  const todayPrefix = new Date().toISOString().slice(0, 10);
  const openedToday = events.filter(
    (e) => e.type === "tab_event" && e.event === "open" && e.ts && e.ts.startsWith(todayPrefix)
  ).length;
  document.getElementById("opened-today").textContent = openedToday;

  // Oldest tab
  const tabTimes = await chrome.storage.local.get("tabCreatedAt");
  const times = tabTimes.tabCreatedAt || {};
  let oldestId = null;
  let oldestTs = null;
  for (const [id, ts] of Object.entries(times)) {
    if (!oldestTs || ts < oldestTs) {
      oldestTs = ts;
      oldestId = Number(id);
    }
  }

  const oldestEl = document.getElementById("oldest-tab");
  if (oldestId !== null) {
    try {
      const tab = await chrome.tabs.get(oldestId);
      const ageMs = Date.now() - new Date(oldestTs).getTime();
      const ageStr = formatAge(ageMs);
      oldestEl.textContent = `${ageStr} — ${tab.title || tab.url || "untitled"}`;
    } catch {
      oldestEl.textContent = oldestTs ? `since ${oldestTs.slice(0, 16)}` : "—";
    }
  } else {
    oldestEl.textContent = "—";
  }

  // Native host status
  checkNativeHost();
}

function formatAge(ms) {
  const min = Math.floor(ms / 60000);
  if (min < 60) return `${min}m`;
  const hours = Math.floor(min / 60);
  if (hours < 24) return `${hours}h ${min % 60}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

function checkNativeHost() {
  const el = document.getElementById("host-status");
  try {
    chrome.runtime.sendNativeMessage("com.eidos.aad.browser", { type: "ping" }, (response) => {
      if (chrome.runtime.lastError) {
        el.textContent = "not connected";
        el.className = "host-status disconnected";
      } else {
        el.textContent = "connected";
        el.className = "host-status connected";
      }
    });
  } catch {
    el.textContent = "not connected";
    el.className = "host-status disconnected";
  }
}

// Export buffered events as NDJSON download
document.getElementById("export-btn").addEventListener("click", async () => {
  const data = await chrome.storage.local.get("events");
  const events = data.events || [];
  const ndjson = events.map((e) => JSON.stringify(e)).join("\n") + "\n";
  const blob = new Blob([ndjson], { type: "application/x-ndjson" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `aad-browser-${new Date().toISOString().slice(0, 10)}.ndjson`;
  a.click();
  URL.revokeObjectURL(url);
});

// Manual snapshot trigger
document.getElementById("snapshot-btn").addEventListener("click", async () => {
  // Send message to background to take snapshot
  chrome.runtime.sendMessage({ action: "snapshot" });
  // Brief visual feedback
  const btn = document.getElementById("snapshot-btn");
  btn.textContent = "done!";
  setTimeout(() => (btn.textContent = "Snapshot now"), 1000);
});

render();
