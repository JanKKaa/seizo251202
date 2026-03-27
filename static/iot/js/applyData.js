function esc(txt){
  return (txt==null?'':String(txt)).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}


window.esp32AlarmCache = window.esp32AlarmCache || {};

// Fallback: nếu hệ thống chưa định nghĩa showAlarmGif ở file khác
// - Nếu có element phù hợp thì bật/tắt hiển thị
// - Nếu không có element thì im lặng (no-op) để tránh spam console
window.showAlarmGif = window.showAlarmGif || function (hasAlarm) {
  const ids = ['alarm-gif', 'alarmGif', 'alarm-gif-container', 'alarmGifContainer'];
  let el = null;

  for (const id of ids) {
    el = document.getElementById(id);
    if (el) break;
  }
  if (!el) {
    // thử theo class (nếu bạn dùng class thay vì id)
    el = document.querySelector('.alarm-gif, .alarmGif');
  }
  if (!el) return;

  // Toggle đơn giản
  el.style.display = hasAlarm ? '' : 'none';
  el.classList.toggle('active', !!hasAlarm);
};

// --- NEW: Alarm state broadcaster (đảm bảo "có alarm => về màn hình 1") ---
window.__alarmStateCache = window.__alarmStateCache || { general: null, net100: null, esp32: null };

function publishAlarmState(partial = {}) {
  // cập nhật từng phần
  if (partial.net100 != null) window.net100AlarmCount = Number(partial.net100) || 0;
  if (partial.esp32  != null) window.esp32AlarmCount  = Number(partial.esp32)  || 0;

  // general = OR của các nguồn
  const g = ((Number(window.net100AlarmCount) || 0) > 0 || (Number(window.esp32AlarmCount) || 0) > 0) ? 1 : 0;
  window.alarmCount = g;

  // tránh spam event nếu không đổi
  const next = { 
    general: g, 
    net100: Number(window.net100AlarmCount) || 0, 
    esp32: Number(window.esp32AlarmCount) || 0 
  };
  const prev = window.__alarmStateCache;

  const changed =
    prev.general !== next.general ||
    prev.net100 !== next.net100 ||   // <-- Sửa lại dòng này, bỏ ||s
    prev.esp32 !== next.esp32;

  if (changed) {
    window.__alarmStateCache = next;
    window.dispatchEvent(new CustomEvent('alarm:update', { detail: next }));
  }
}

// --- Mail notification queue & luân phiên hiển thị ---

let mailQueue = [];
let mailQueueIndex = 0;
let mailQueueTimer = null;

// Hàm hiển thị mail theo queue, luân phiên mỗi 10 giây
function showNextMailNotification() {
    if (mailQueue.length === 0) {
        hideMailNotification();
        mailQueueIndex = 0;
        return;
    }
    // Lấy mail hiện tại trong queue
    const mail = mailQueue[mailQueueIndex];
    const message = `[${mail.sender}] ${mail.message}`;
    const level = mail.level || mail.priority;
    showMailNotification(message, level);

    // Tính thời gian hiển thị: lấy min(thời gian theo level, 10 giây)
    let levelTimeout = 120000;
    if (level == 3) levelTimeout = 500000;
    else if (level == 2) levelTimeout = 300000;
    else if (level == 1) levelTimeout = 120000;
    const timeout = Math.min(levelTimeout, 10000); // 10 giây hoặc thời gian theo level

    clearTimeout(mailQueueTimer);
    mailQueueTimer = setTimeout(() => {
        mailQueueIndex = (mailQueueIndex + 1) % mailQueue.length;
        showNextMailNotification();
    }, timeout);
}

// Hàm kiểm tra và cập nhật queue mail
function checkAndShowMailNotification(notifs) {
    // SAFE: đảm bảo arr luôn là mảng (tránh crash khi payload khác dự kiến)
    const arr = Array.isArray(notifs?.notifications)
      ? notifs.notifications
      : (Array.isArray(notifs) ? notifs : []);

    // Lấy tất cả thông báo có priority hoặc level (mail)
    mailQueue = arr.filter(n => n && (n.priority || n.level));
    mailQueueIndex = 0;
    clearTimeout(mailQueueTimer);
    if (mailQueue.length > 0) {
        showNextMailNotification();
    } else {
        hideMailNotification();
    }
}

// Hàm hiển thị mail notification với thời gian theo level (giây -> mili giây)
function showMailNotification(message, level) {
    const ticker = document.getElementById('dashboard-ticker');
    const mailTicker = document.getElementById('mail-notification-ticker');
    const mailContent = document.getElementById('mail-notification-content');
    if (ticker) ticker.style.display = 'none';
    if (mailTicker && mailContent) {
        mailContent.textContent = message;
        mailTicker.style.display = 'flex';
        // Thêm class để đổi màu qua CSS
        mailTicker.classList.add('mail-active');
        // Quy định thời gian hiển thị theo level (giây -> mili giây)
        let timeout = 120000;
        if (level == 3) timeout = 500000;
        else if (level == 2) timeout = 300000;
        else if (level == 1) timeout = 120000;
        clearTimeout(window._mailNotifyTimeout);
        window._mailNotifyTimeout = setTimeout(hideMailNotification, timeout);
    }
}

// Hàm ẩn mail notification và hiện lại ticker thường
function hideMailNotification() {
    const ticker = document.getElementById('dashboard-ticker');
    const mailTicker = document.getElementById('mail-notification-ticker');
    if (mailTicker) {
        mailTicker.style.display = 'none';
        // Xóa class để trả về màu mặc định
        mailTicker.classList.remove('mail-active');
    }
    if (ticker) ticker.style.display = '';
    clearTimeout(mailQueueTimer);
    mailQueue = [];
    mailQueueIndex = 0;
}


window.updateDashboardTicker = (function() {
    let lastNotifications = [];
    let lastLogo = '';
    let tickerIndex = 0;
    let tickerTimer = null;
    return function(data) {
        applyThemeFromBackend(data.theme);

        const ticker = document.getElementById('dashboard-ticker');
        const tickerContent = document.getElementById('dashboard-marquee-content');
        if (!tickerContent || !ticker) return;

        checkAndShowMailNotification(data);

        const mailTicker = document.getElementById('mail-notification-ticker');
        if (mailTicker && mailTicker.style.display === 'flex') return;

        lastNotifications = Array.isArray(data.notifications) ? data.notifications : [];
        

        tickerIndex = 0;
        clearTimeout(tickerTimer);

        function showTickerItem(idx) {
            if (!lastNotifications.length) {
                tickerContent.innerHTML =  `<span class="greeting-msg">${esc(data.greeting || '')}</span>`;
                autoFitTickerFont();
                return;
            }
            const msg = lastNotifications[idx % lastNotifications.length];
            let html = lastLogo;
            if (msg.type === 'greeting') {
                html += `<span class="greeting-msg ${esc(msg.effect)}">${esc(msg.message)}</span>`;
            } else if (msg.type === 'inspiration') {
                html += `<span class="inspiration-msg ${esc(msg.effect)}">
                            <div>${esc(msg.jp)}</div>
                            <div>${esc(msg.vi)}</div>
                         </span>`;
            } else if (msg.type === 'mail') {
                // Nếu message dài hơn 40 ký tự, giảm font-size
                const isLong = (msg.message && msg.message.length > 40);
                html += `<span class="mail-msg ${esc(msg.effect)}${isLong ? ' long-mail' : ''}">${esc(msg.message)}</span>`;
            }
            tickerContent.innerHTML = html;
            autoFitTickerFont();
        }

        showTickerItem(tickerIndex);

        tickerTimer = setInterval(function() {
            tickerIndex = (tickerIndex + 1) % lastNotifications.length;
            showTickerItem(tickerIndex);
        }, 10000);
    };
})();

const lastKpiValues = {
  total: null,
  production: null,
  stop: null,
  alarm: null,
  offline: null,
  arrange: null,
  now: null
};

window.applyData = function(data){
  const numberFmt = new Intl.NumberFormat('ja-JP');

  function renderMachineCard(m) {
    const status = m.runtime_status_code || 'unknown';
    const flashClass = m.status_changed ? ` status-change-flash status-change-flash-${status}` : '';
    // Hiển thị tên sản phẩm phía dưới cùng card (lấy từ m.plan_products[0])
    return `<div class="machine-card card-status-${status}${flashClass}" data-status="${status}">
      <div class="machine-card-header text-center">
        <div class="alarm-count">
            <span class="alarm-num">${m.alarm_count != null ? m.alarm_count : 0}</span>
          </div>
        <span class="machine-name">${esc(m.name||m.address)}</span>
        <span class="machine-status badge badge-info ${status}">${esc(m.runtime_status_jp||'')}</span>
      </div>
      <div class="machine-card-body text-center">      
        <div class="shot-ct">
          <span>SHOT: ${numberFmt.format(m.shotno != null ? m.shotno : 0)}</span>
          <span>CT: ${esc(m.cycletime != null ? m.cycletime : '0.00')}s</span>
          
        </div>
        <div class="product-name">${esc((m.plan_products && m.plan_products[0]) || '')}</div>
      </div>
    </div>`;
  }
  // Lọc: chỉ giữ máy có kế hoạch (plan_in_today === true)
  const factory1Planned = (data.machines_factory1 || []).filter(m => m.plan_in_today === true);
  const factory2Planned = (data.machines_factory2 || []).filter(m => m.plan_in_today === true);

  function renderCardList(list){ return list.map(renderMachineCard).join(''); }

  // Render Factory 1 (chỉ máy có kế hoạch)
  const factory1Html = renderCardList(factory1Planned);
  const factory1Grid = document.getElementById('factory1-grid');
  if (factory1Grid && factory1Html !== window._lastFactory1Html) {
    factory1Grid.innerHTML = factory1Html;
    window._lastFactory1Html = factory1Html;
  }

  // Render Factory 2 (chỉ máy có kế hoạch)
  const factory2Html = renderCardList(factory2Planned);
  const factory2Grid = document.getElementById('factory2-grid');
  if (factory2Grid && factory2Html !== window._lastFactory2Html) {
    factory2Grid.innerHTML = factory2Html;
    window._lastFactory2Html = factory2Html;
  }

  // KPI giữ nguyên
  function updateKpi(id, value, key) {
    const el = document.getElementById(id);
    if (!el) return;
    if (lastKpiValues[key] !== value) {
      el.textContent = value;
      lastKpiValues[key] = value;
    }
  }
  updateKpi('kpi-total',      data.total != null ? data.total : 0,      'total');
  updateKpi('kpi-production', data.production != null ? data.production : 0, 'production');
  updateKpi('kpi-stop',       data.stop != null ? data.stop : 0,        'stop');
  updateKpi('kpi-alarm',      data.alarm != null ? data.alarm : 0,      'alarm');
  updateKpi('kpi-offline',    data.offline != null ? data.offline : 0,  'offline');
  updateKpi('kpi-arrange',    data.arrange != null ? data.arrange : 0,  'arrange');
  updateKpi('last-update-label', '更新: ' + (data.now != null ? data.now : '--:--:--'), 'now');

  // Popup alarm (vẫn dựa trên danh sách gốc để không mất cảnh báo của máy không có kế hoạch, nếu muốn cũng lọc thì thay bằng factory1Planned/factory2Planned)
  if(document.getElementById('alarm-popup-list')) {
    document.getElementById('alarm-popup-list').innerHTML =
      (data.machines_factory1||[]).map(renderAlarmPopup).join('') +
      (data.machines_factory2||[]).map(renderAlarmPopup).join('');
  }

  const hasAlarm =
    (data.machines_factory1||[]).some(m => m.alarm_active || m.runtime_status_code === 'alarm')
    || (data.machines_factory2||[]).some(m => m.alarm_active || m.runtime_status_code === 'alarm');

  window.showAlarmGif(hasAlarm);

  // --- UPDATED: cập nhật alarm realtime cho main.js + modal logic ---
  const net100Active = hasAlarm ? 1 : 0;

  const esp32PopupList = document.getElementById('esp32-alarm-popup-list');
  const esp32ActiveFallback = esp32PopupList ? esp32PopupList.children.length : (Number(window.esp32AlarmCount) || 0);

  publishAlarmState({ net100: net100Active, esp32: esp32ActiveFallback });

  // Gán danh sách máy đang alarm cho window.alarmMachines
  window.alarmMachines = [
    ...(data.machines_factory1 || []),
    ...(data.machines_factory2 || []),
    ...(data.machines_esp32 || [])
  ].filter(m => m.alarm_active === true || m.runtime_status_code === 'alarm');
};

function renderAlarmPopup(m){
  const st = m.runtime_status_code || m.rt_runtime_status_code;
  const active = m.alarm_active === true || st === 'alarm';
  if(!active) return '';
  const name = esc(m.name||m.rt_name||'');
  const latest = m.latest_alarm || {};
  const code    = latest.alarm_code   || '';
  const aname   = latest.alarm_name   || '';
  const content = latest.alarm_content|| '';
  const timeRaw = latest.alarm_time   || '';
  let timeStr = '';
  if(timeRaw){
    try{
      const d = new Date(timeRaw);
      timeStr = isNaN(d) ? String(timeRaw)
        : String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');
    }catch(_){}
  }
  const timeHtml = timeStr ? `<span style="font-size:.85rem;color:#ffe3e3;">${esc(timeStr)}</span>` : '';
  let detail = '';
  if(code || aname || content){
    detail = `<div class="alarm-detail">
      ${esc(code)} ${esc(aname)}<br>
      <span style="font-size:.72rem;color:#ffe3e3;">${esc(content)}</span>
    </div>`;
  } else {
    detail = `<div class="alarm-detail">アラーム</div>`;
  }
  return `<div class="alarm-popup" role="alert" aria-live="assertive">
    <div class="alarm-title">
      <i class="fas fa-exclamation-triangle"></i>
      <span style="color:#fff200;font-weight:700;">${name}</span>
      ${timeHtml}
    </div>
    ${detail}
  </div>`;
}

// ...existing code...

function applyThemeFromBackend(theme) {
    const header = document.querySelector('.dashboard-header');
    const ticker = document.getElementById('dashboard-ticker');
    if (header) {
        header.className = 'dashboard-header theme-' + (theme || 'default');
    }
    if (ticker) {
        ticker.className = 'dashboard-ticker theme-' + (theme || 'default');
    }
}

// Khi nhận dữ liệu từ backend:
function fetchAndUpdateTicker() {
    fetchWithKeepAlive('/iot/ticker_view')
        .then(res => res.json())
        .then(data => {
            window.updateDashboardTicker(data);
        })
        .catch(err => console.error('Ticker API error:', err));
}
window.addEventListener('DOMContentLoaded', fetchAndUpdateTicker);
setInterval(fetchAndUpdateTicker, 30000);

// ...existing code...

function renderOeeTable(list) {
  if (!list || !list.length) return '<div style="color:#888;">データなし</div>';
  return `<table class="table table-sm table-bordered" style="font-size:0.95em;">
    <thead><tr><th>機械名</th><th>可動率(%)</th><th>性能(%)</th><th>品質(%)</th><th>OEE(%)</th></tr></thead>
    <tbody>
      ${list.map(item => `<tr>
        <td>${esc(item.name)}</td>
        <td style="text-align:right;">${item.availability}</td>
        <td style="text-align:right;">${item.performance}</td>
        <td style="text-align:right;">${item.quality}</td>
        <td style="text-align:right;font-weight:bold;">${item.oee}</td>
      </tr>`).join('')}
    </tbody>
  </table>`;
}

function updateOeeSummary() {
  fetchWithKeepAlive('/iot/oee_today')
    .then(res => res.json())
    .then(data => {
      document.getElementById('oee-summary').innerHTML = renderOeeTable(data.oee);
    });
}
window.addEventListener('DOMContentLoaded', updateOeeSummary);

// Hàm cập nhật top 5 máy có nhiều alarm nhất trong tháng
function updateAlarmTop5Machines() {
  fetchWithKeepAlive('/iot/alarm_top5_machine_month')
    .then(res => res.json())
    .then(data => {
      document.getElementById('alarm-top5-summary').innerHTML = renderAlarmTop5Machines(data.machines);
    });
}

function renderAlarmTop5Machines(list) {
  if (!list || !list.length) return '<div class="text-muted">データなし</div>';
  return `<div class="alarm-top5-cards-row">
    ${list.map((item, idx) => `
      <div class="card shadow-sm text-center card-top5-${idx}">
        <div class="card-body d-flex flex-row justify-content-center align-items-center">
          <span class="badge bg-${idx===0?'danger':idx===1?'warning':'info'}">${idx+1}</span>
          <span class="fw-bold">${esc(item.machine__name||'')}</span>
          <span class="text-danger fw-bold">${item.alarm_count||0} 回</span>
        </div>
      </div>
    `).join('')}
  </div>`;
}
// Đảm bảo gọi updateAlarmTop5Machines() để cập nhật nội dung vào #alarm-top5-summary

// Đảm bảo gọi updateAlarmTop5Machines() khi cần cập nhật bảng top 5 máy alarm
// Ví dụ:
window.addEventListener('DOMContentLoaded', () => {
  updateAlarmTop5Machines();
  setInterval(updateAlarmTop5Machines, 15000); // Cập nhật mỗi 15 giây
});

window.ESP32_STATIC_LIST = window.ESP32_STATIC_LIST || [
  { address: "2",  name: "2号機",  condname: "", shotno: 0, cycletime: "0.00" },
  { address: "8",  name: "8号機",  condname: "", shotno: 0, cycletime: "0.00" },
  { address: "10", name: "10号機", condname: "", shotno: 0, cycletime: "0.00" },
  { address: "12", name: "12号機", condname: "", shotno: 0, cycletime: "0.00" },
  { address: "28", name: "28号機", condname: "", shotno: 0, cycletime: "0.00" },
];

function renderEsp32Card(m) {
  const status = m.runtime_status_code || 'unknown';
  const flashClass = m.status_changed ? ` status-change-flash status-change-flash-${status}` : '';
  const alarmCount = getAlarmCount(m);
  // Đảm bảo lấy tên sản phẩm từ kế hoạch (m.plan_products[0]) nếu có
  return `<div class="machine-card card-status-${status}${flashClass}" data-status="${status}">
    <div class="machine-card-header text-center" style="display:flex;align-items:center;justify-content:space-between;">
      <div class="alarm-count" style="margin-right:10px;">
        <span class="alarm-num" style="color:#d32f2f;">${alarmCount}</span>
      </div>
      <span class="machine-name">${esc(m.name||m.address)}</span>
      <span class="machine-status badge badge-info ${status}">${esc(m.runtime_status_jp||'')}</span>
    </div>
    <div class="machine-card-body text-center">
      <div class="condname">${esc(m.condname||'')}</div>
      <div class="shot-ct">
        <span>SHOT: ${m.shotno != null ? m.shotno : 0}</span>
        <span>CT: ${esc(m.cycletime != null ? m.cycletime : '0.00')}s</span>
      </div>
      <div class="product-name">${esc((m.plan_products && m.plan_products[0]) || '')}</div>
    </div>
  </div>`;
}

let lastEsp32Html = '';

// NOTE: File đang có 2 hàm renderEsp32Grid(). HÀM Ở CUỐI FILE đã ghi đè hàm này.
// Để tránh thay đổi hành vi, chỉ cần XÓA bản định nghĩa ở đây và giữ bản ở cuối file.
// (Không thay đổi logic runtime vì hiện tại JS vẫn dùng bản ở cuối.)
// --- DELETE BLOCK START ---
// function renderEsp32Grid(machines) {
//   const grid = document.getElementById('esp32-grid');
//   if (!grid) return;
//
//   const plannedNames = getPlannedNames('F1');
//   const plannedSet = new Set(plannedNames);
//
//   function esp32Planned(m){
//     if (m.plan_in_today === true) return true;
//     if (m.in_plan === true) return true;
//     const baseName = String(m.name || m.address || '');
//     if (plannedSet.has(baseName)) return true;
//     for (const nm of plannedSet) {
//       if (nm.startsWith(baseName + ' ') || nm.startsWith(baseName + ' -')) return true;
//     }
//     return false;
//   }
//
//   const filtered = (machines || []).filter(esp32Planned);
//
//   let html;
//   if (!filtered.length) {
//     html = '<div class="text-muted"> </div>';
//   } else {
//     html = filtered.map(renderEsp32Card).join('');
//   }
//
//   if (html !== lastEsp32Html) {
//     grid.innerHTML = html;
//     lastEsp32Html = html;
//   }
// }
// --- DELETE BLOCK END ---

// ...existing code...

function renderEsp32Grid(machines) {
  const grid = document.getElementById('esp32-grid');
  if (!grid) return;

  const plannedNames = getPlannedNames('F1');
  const plannedSet = new Set(plannedNames);

  function esp32Planned(m){
    if (m.plan_in_today === true || m.in_plan === true) return true;
    const base = String(m.name||m.address||'');
    if (plannedSet.has(base)) return true;
    for (const nm of plannedSet){
      if (nm.startsWith(base+' ') || nm.startsWith(base+' -')) return true;
    }
    return false;
  }

  const filtered = (machines||[]).filter(esp32Planned);
  const html = filtered.length
    ? filtered.map(renderEsp32Card).join('')
    : '<div class="text-muted"> </div>';

  if (html !== lastEsp32Html){
    grid.innerHTML = html;
    lastEsp32Html = html;
  }
}

// --- Tối ưu fetch: Sử dụng keep-alive ---
function fetchWithKeepAlive(url) {
  return fetch(url, { headers: { 'Connection': 'keep-alive' } });
}

// Ví dụ sử dụng cho ESP32 fetch:
function fetchAndRenderEsp32() {
  fetchWithKeepAlive('/iot/api/esp32_machines/')
    .then(res => res.json())
    .then(data => {
      // Nếu dữ liệu không hợp lệ hoặc thiếu, dùng giá trị gần nhất hoặc mặc định
      let machines = [];
      if (data && Array.isArray(data.machines) && data.machines.length > 0) {
        machines = data.machines;
        // Lưu lại giá trị gần nhất vào cache
        window.esp32AlarmCache.lastMachines = machines;
      } else if (window.esp32AlarmCache.lastMachines) {
        // Nếu API lỗi, dùng dữ liệu gần nhất đã lưu
        machines = window.esp32AlarmCache.lastMachines;
      } else {
        // Nếu chưa có dữ liệu, dùng danh sách mặc định
        machines = window.ESP32_STATIC_LIST || [];
      }
      renderEsp32Grid(machines);
    })
    .catch(() => {
      // Nếu fetch lỗi, dùng dữ liệu gần nhất hoặc mặc định
      let machines = window.esp32AlarmCache.lastMachines || window.ESP32_STATIC_LIST || [];
      renderEsp32Grid(machines);
      const grid = document.getElementById('esp32-grid');
      if (grid && (!machines || machines.length === 0)) {
        grid.innerHTML = '<div class="text-danger">ESP32データ取得エラー</div>';
      }
    });
}

window.addEventListener('DOMContentLoaded', fetchAndRenderEsp32);
setInterval(fetchAndRenderEsp32, 200);

function renderEsp32AlarmPopup(m) {
  // Có thể dùng lại renderAlarmPopup hoặc tuỳ chỉnh giao diện
  const name = esc(m.address);
  return `<div class="alarm-popup esp32-alarm" role="alert" aria-live="assertive">
    <div class="alarm-title">
      <i class="fas fa-exclamation-triangle"></i>
      <span style="color:#fff200;font-weight:700;">${name}</span>
    </div>
    <div class="alarm-detail">アラーム</div>
  </div>`;
}

let lastEsp32AlarmHtml = '';
function fetchAndRenderEsp32AlarmPopup() {
  fetchWithKeepAlive('/iot/api/esp32_alarm_popup/')
    .then(res => res.json())
    .then(data => {
      const alarms = Array.isArray(data.machines) ? data.machines : [];
      const popupList = document.getElementById('esp32-alarm-popup-list');

      if (popupList) {
        const html = alarms.map(renderEsp32AlarmPopup).join('');
        if (html !== lastEsp32AlarmHtml) {
          popupList.innerHTML = html;
          lastEsp32AlarmHtml = html;
        }
      }

      // --- NEW: ESP32 alarm realtime -> ép về màn hình 1 ngay cả khi NET100 không alarm
      publishAlarmState({ esp32: alarms.length });
    })
    .catch(() => {
      // nếu lỗi API, giữ nguyên trạng thái trước đó (không ép sai)
    });
}

// Gọi hàm này khi cần cập nhật popup ESP32 (ví dụ mỗi 1 giây)
setInterval(fetchAndRenderEsp32AlarmPopup, 1000);
window.addEventListener('DOMContentLoaded', fetchAndRenderEsp32AlarmPopup);

function autoFitTickerFont() {
    const tickerContent = document.getElementById('dashboard-marquee-content');
    if (!tickerContent) return;
    let fontSize = 32;
    tickerContent.style.fontSize = fontSize + 'px';
    // Giảm font-size đến khi vừa khung cả chiều rộng và chiều cao
    while (
        (tickerContent.scrollWidth > tickerContent.offsetWidth ||
         tickerContent.scrollHeight > tickerContent.offsetHeight) &&
        fontSize > 14
    ) {
        fontSize -= 2;
        tickerContent.style.fontSize = fontSize + 'px';
    }
}

function getAlarmCount(m) {
  if (m.alarm_count != null) return m.alarm_count;
  if (m.latest_alarm && m.latest_alarm.count != null) return m.latest_alarm.count;
  return 0;
}
function pollMailNotification() {
    fetch('/iot/dashboard_notifications_json/')
        .then(res => res.json())
        .then((data) => {
            // Nếu không còn notification, ẩn mail notification
            if (!data.notifications || data.notifications.length === 0) {
                hideMailNotification();
            }
        });
}
setInterval(pollMailNotification, 10000); // Kiểm tra mỗi 10 giây

function getPlannedNames(factory){
  const id = factory === 'F1' ? '__pmf1' : '__pmf2';
  const el = document.getElementById(id);
  try {
    const arr = el ? JSON.parse(el.textContent) : [];
    return Array.isArray(arr) ? arr.map(String) : [];
  } catch(_){ return []; }
}
// (Giữ đúng một hàm renderEsp32Grid như sau)
function renderEsp32Grid(machines){
  const grid = document.getElementById('esp32-grid');
  if(!grid) return;
  const plannedSet = new Set(getPlannedNames('F1'));
  function esp32Planned(m){
    if (m.plan_in_today === true || m.in_plan === true) return true;
    const base = String(m.name||m.address||'');
    if (plannedSet.has(base)) return true;
    for (const nm of plannedSet){
      if (nm.startsWith(base+' ') || nm.startsWith(base+' -')) return true;
    }
    return false;
  }
  const filtered = (machines||[]).filter(esp32Planned);
  const html = filtered.length
    ? filtered.map(renderEsp32Card).join('')
    : '<div class="text-muted"> </div>';
  if (html !== lastEsp32Html){
    grid.innerHTML = html;
    lastEsp32Html = html;
  }
}

function rebalanceFactory1() {
  const block = document.getElementById('factory1-block');
  if (!block) return;
  const cards = block.querySelectorAll('.machine-card');
  const count = cards.length;
  if (!count) return;
  // Nếu muốn ép số cột chính xác theo số card (1 hàng duy nhất <= viewport đủ rộng):
  // block.style.gridTemplateColumns = `repeat(${count}, minmax(160px,1fr))`;
  // Hoặc giữ auto-fit đã khai báo trong CSS (không làm gì).
}
function layoutFactory1Row() {
  const block = document.getElementById('factory1-block');
  if (!block) return;
  const cards = block.querySelectorAll('#factory1-grid .machine-card, #esp32-grid .machine-card');
  const count = cards.length;
  block.style.gridTemplateColumns = `repeat(${Math.min(count || 1, 6)}, minmax(160px,1fr))`;
}
function layoutFactory2Row() {
  const block = document.getElementById('factory2-block');
  if (!block) return;
  const cards = block.querySelectorAll('#factory2-grid .machine-card');
  const count = cards.length;
  block.style.gridTemplateColumns = `repeat(${Math.min(count || 1, 6)}, minmax(160px,1fr))`;
}
// ...call these after render...

const CHANGE4M_REFRESH_MS = 60000;
let change4mPollHandle = null;
let latestChange4MEntries = [];

function renderChange4MPopup(entries) {
  const list = document.getElementById('change-4m-popup-list');
  const emptyState = document.getElementById('change-4m-popup-empty');
  if (!list || !emptyState) return;

  list.innerHTML = '';
  if (!entries.length) {
    emptyState.hidden = false;
    return;
  }
  emptyState.hidden = true;

  entries.forEach(entry => {
    const item = document.createElement('div');
    item.className = 'list-group-item change-4m-popup-item' + (entry.highlight ? ' highlight' : '');
    const tagsMarkup = Array.isArray(entry.tags) && entry.tags.length
      ? `<div class="change-4m-popup-tags">${entry.tags.map(tag => `<span>${esc(tag)}</span>`).join('')}</div>`
      : '';
    const reporter = entry.reporter ? `<span><i class="bi bi-person-circle me-1"></i>${esc(entry.reporter)}</span>` : '';
    // Bỏ phần thời gian (periodMarkup)
    item.innerHTML = `
      <div class="fw-semibold">${esc(entry.code || '4M')}｜${esc(entry.message)}</div>
      ${entry.detail ? `<div class="text-muted mt-1">${esc(entry.detail)}</div>` : ''}
      <div class="change-4m-popup-meta">
        ${reporter}
        ${entry.sender ? `<span><i class="bi bi-at me-1"></i>${esc(entry.sender)}</span>` : ''}
      </div>
      ${tagsMarkup}
    `;
    list.appendChild(item);
  });
}

function formatChange4MPeriod(startIso, endIso) {
  const startLabel = formatChange4MTime(startIso);
  const endLabel = endIso ? formatChange4MTime(endIso) : '';
  if (!startLabel && !endLabel) return '';
  if (endLabel) return `${startLabel} 〜 ${endLabel}`;
  return `${startLabel} 〜`;
}

function openChange4MPopup() {
  const backdrop = document.getElementById('change-4m-popup-backdrop');
  if (!backdrop) return;
  backdrop.hidden = false;
  renderChange4MPopup(latestChange4MEntries);
  document.body.classList.add('modal-open');
}

function closeChange4MPopup() {
  const backdrop = document.getElementById('change-4m-popup-backdrop');
  if (!backdrop) return;
  backdrop.hidden = true;
  document.body.classList.remove('modal-open');
}

function updateChange4MData(entries) {
  latestChange4MEntries = entries;

  if (typeof window.renderChange4MTicker === 'function') {
    window.renderChange4MTicker(entries);
  } else {
    console.warn('[4M] window.renderChange4MTicker is not ready');
  }

  const backdropVisible = document.getElementById('change-4m-popup-backdrop')?.hidden === false;
  if (backdropVisible) {
    renderChange4MPopup(entries);
  }
}
// ...existing code...

async function fetchChange4MUpdatesFromApi() {
  const endpoint = window.CHANGE4M_ENDPOINT || '/iot/api/change-4m/';
  try {
    const response = await fetch(endpoint, { cache: 'no-store' });
    if (!response.ok) throw new Error(`[4M ticker] HTTP ${response.status}`);
    const payload = await response.json();
    const entries = Array.isArray(payload.entries) ? payload.entries : [];
    updateChange4MData(entries);
  } catch (error) {
    console.warn('[4M ticker] fetch failed', error);
  }
}

function ensureChange4MPolling() {
  if (change4mPollHandle) clearInterval(change4mPollHandle);
  change4mPollHandle = setInterval(() => {
    fetchChange4MUpdatesFromApi();
  }, CHANGE4M_REFRESH_MS);
}

function renderChange4MTicker(entries) {
  const container = document.getElementById('change-4m-ticker');
  if (!container) return;
  if (!Array.isArray(entries) || !entries.length) {
    container.innerHTML = '<div class="text-muted text-center">特に変更はありません</div>';
    return;
  }
  const html = entries.map(entry => {
    // Bỏ phần thời gian (period)
    return `
      <div class="change-4m-ticker-item">
        <span class="change-4m-ticker-code">${esc(entry.code || '4M')}</span>
        <span class="change-4m-ticker-message">${esc(entry.message)}</span>
      </div>
    `;
  }).join('');
  container.innerHTML = html;
}

// ...existing code...
if (typeof window !== 'undefined') {
  window.renderChange4MTicker = renderChange4MTicker;
  window.dispatchEvent(new Event('change4m:ticker-ready'));
  window.addEventListener('change4m:update', evt => updateChange4MData(evt.detail || []));
  document.addEventListener('DOMContentLoaded', () => {
    const openBtn = document.getElementById('change-4m-popup-open');
    const closeBtn = document.getElementById('change-4m-popup-close');
    const backdrop = document.getElementById('change-4m-popup-backdrop');

    if (openBtn) openBtn.addEventListener('click', openChange4MPopup);
    if (closeBtn) closeBtn.addEventListener('click', closeChange4MPopup);
    if (backdrop) {
      backdrop.addEventListener('click', evt => {
        if (evt.target === backdrop) closeChange4MPopup();
      });
    }
    document.addEventListener('keydown', evt => {
      if (evt.key === 'Escape') closeChange4MPopup();
    });

    if (Array.isArray(window.__INITIAL_CHANGE4M_UPDATES__) && window.__INITIAL_CHANGE4M_UPDATES__.length) {
      updateChange4MData(window.__INITIAL_CHANGE4M_UPDATES__);
    } else {
      fetchChange4MUpdatesFromApi();
    }
    ensureChange4MPolling();
  });
}

function formatChange4MTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  if (isNaN(d)) return '';
  // Hiển thị dạng YYYY/MM/DD HH:mm hoặc chỉ HH:mm nếu cùng ngày
  const y = d.getFullYear();
  const m = ('0' + (d.getMonth() + 1)).slice(-2);
  const day = ('0' + d.getDate()).slice(-2);
  const h = ('0' + d.getHours()).slice(-2);
  const min = ('0' + d.getMinutes()).slice(-2);
  return `${y}/${m}/${day} ${h}:${min}`;
}


