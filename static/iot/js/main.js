// File: main.js
document.addEventListener('DOMContentLoaded', function() {
  let currentScreen = 1;             
  let autoSwitchTimeout = null;      

  // Cấu hình địa chỉ IP của ESP32 (Kiểm tra lại IP này trong mạng công ty)
  const ESP32_URL = "http://192.168.11.40";

  const alarmState = {
    general: Number(window.alarmCount) || 0,
    net100: Number(window.net100AlarmCount || window.net100AlarmActive) || 0,
    esp32: Number(window.esp32AlarmCount || window.esp32AlarmActive) || 0,
  };

  const hasActiveAlarm = () =>
    alarmState.general > 0 || alarmState.net100 > 0 || alarmState.esp32 > 0;

  function applyScreen() {
    const s1 = document.getElementById('screen1');
    const s2 = document.getElementById('screen2');
    if (!s1 || !s2) return;
    s1.style.display = currentScreen === 1 ? '' : 'none';
    s2.style.display = currentScreen === 2 ? '' : 'none';
  }
  applyScreen();

  function stopAutoSwitch() {
    if (autoSwitchTimeout) {
      clearTimeout(autoSwitchTimeout);
      autoSwitchTimeout = null;
    }
  }

  // Danh sách máy Factory 1 (giống FACTORY1_IDS ở backend)
  const FACTORY1_IDS = [1, 2, 3, 4, 5, 6, 9, 10, 12, 13, 27, 28];

  // Hàm xác định alarm thuộc xưởng nào
  window.getAlarmFactory = function() {
  const alarmMachines = (window.alarmMachines || []).filter(
    m =>
      m.runtime_status_code === "alarm" ||   // máy NET100
      m.alarm_active === true                // máy ESP32
  );

  let hasF1 = false, hasF2 = false;

  for (const m of alarmMachines) {
    const mNum = Number((m.name || m.address || '').match(/^(\d+)/)?.[1]);
    if (FACTORY1_IDS.includes(mNum)) hasF1 = true;
    else hasF2 = true;
  }

  if (hasF1 && hasF2) return 3;
  if (hasF1) return 1;
  if (hasF2) return 2;
  return 0;
}

  window.sendSignalToESP32 = async function(action) {
    let factory = getAlarmFactory();
    // Gửi endpoint có dạng: /iot/control-relay/on/?factory=1 hoặc factory=2
    const proxyUrl = `/iot/control-relay/${action}/?factory=${factory}`;
    console.log("Đang gửi tín hiệu đến: " + proxyUrl);
    try {
      const response = await fetch(proxyUrl);
      if (response.ok) {
        console.log("Thành công: ESP32 đã nhận lệnh " + action + " (factory " + factory + ")");
      } else {
        console.error("Lỗi hệ thống Django (404 hoặc 500)");
      }
    } catch (error) {
      console.error("Lỗi kết nối mạng:", error);
    }
  }
  
  function startAutoSwitch() {
    if (hasActiveAlarm()) {
      stopAutoSwitch();
      if (currentScreen !== 1) {
        currentScreen = 1;
        applyScreen();
      }
      return;
    }
    stopAutoSwitch();
    const duration = currentScreen === 1 ? 5 * 60 * 1000 : 2 * 60 * 1000;
    autoSwitchTimeout = setTimeout(() => {
      currentScreen = currentScreen === 1 ? 2 : 1;
      applyScreen();
      startAutoSwitch();
    }, duration);
  }

  let lastAlarmState = null; // Thêm biến này ở đầu file

  function handleAlarmChange(partial = {}) {
    if (partial.general != null) alarmState.general = Number(partial.general) || 0;
    if (partial.net100  != null) alarmState.net100  = Number(partial.net100)  || 0;
    if (partial.esp32   != null) alarmState.esp32   = Number(partial.esp32)   || 0;

    const nowAlarm = hasActiveAlarm();
    if (nowAlarm !== lastAlarmState) {
      // Chỉ gửi lệnh khi trạng thái alarm thay đổi
      if (nowAlarm) {
        stopAutoSwitch();
        if (currentScreen !== 1) {
          currentScreen = 1;
          applyScreen();
        }
        sendSignalToESP32("on");
      } else {
        startAutoSwitch();
        sendSignalToESP32("off");
      }
      lastAlarmState = nowAlarm;
    }
  }

  function switchToScreen1() {
    currentScreen = 1;
    applyScreen();
    startAutoSwitch();
  }

  // Khởi tạo trạng thái ban đầu
  startAutoSwitch();
  if (hasActiveAlarm()) {
    sendSignalToESP32("on");
  } else {
    sendSignalToESP32("off");
  }

  window.updateAlarmSources = handleAlarmChange;
  window.addEventListener('alarm:update', e => handleAlarmChange(e.detail || {}));

  const btnSwitch = document.getElementById('switchScreenBtn');
  if (btnSwitch) {
    btnSwitch.onclick = () => {
      currentScreen = hasActiveAlarm() ? 1 : (currentScreen === 1 ? 2 : 1);
      applyScreen();
      startAutoSwitch();
    };
  }

  window.addEventListener('open4MPopup', switchToScreen1);
  window.addEventListener('openChatworkPopup', switchToScreen1);
});