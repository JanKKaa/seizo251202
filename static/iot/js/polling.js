const DASHBOARD_POLL_MS = 3000;

let pollTimerId = null;
let inFlight = false;

function scheduleNext() {
  if (pollTimerId) clearTimeout(pollTimerId);
  pollTimerId = setTimeout(fetchData, DASHBOARD_POLL_MS);
}

function fetchData() {
  if (inFlight) return;
  inFlight = true;

  fetch('/iot/dashboard_json?_=' + Date.now(), { cache: 'no-store' })
    .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
    .then(data => {

      // 🔥 Thêm dòng này ngay sau khi nhận data
      window.alarmMachines = [
        ...(data.machines_factory1 || []),
        ...(data.machines_factory2 || []),
        ...(data.machines_esp32 || [])
      ];

      // Gọi hàm applyData như cũ
      if (typeof window.applyData === 'function') {
        window.applyData(data);
      } else {
        console.warn('[polling] window.applyData is not a function (script load order?)');
      }
    })
    .catch(e => {
      console.error('Dashboard fetch error', e);
    })
    .finally(() => {
      inFlight = false;
      if (!document.hidden) scheduleNext();
    });
}

function startPolling() {
  if (pollTimerId) return; // tránh start 2 lần
  fetchData();
}

function stopPolling() {
  if (pollTimerId) {
    clearTimeout(pollTimerId);
    pollTimerId = null;
  }
}

window.addEventListener('load', startPolling, { once: true });
document.addEventListener('visibilitychange', () => {
  if (document.hidden) stopPolling();
  else startPolling();
});
