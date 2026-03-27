(function initQAStageAudio(windowObj) {
  const STORAGE_KEY = "qa_stage_sound_enabled";
  let enabled = localStorage.getItem(STORAGE_KEY);
  enabled = enabled === null ? true : enabled === "1";

  let audioCtx = null;
  let unlocked = false;
  let pendingSuccess = false;

  function ensureAudio() {
    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtx.state === "suspended") {
        audioCtx.resume();
      }
      unlocked = true;
      return true;
    } catch (e) {
      return false;
    }
  }

  function tone(freq, durationMs, gainValue, delayMs) {
    if (!enabled) return;
    if (!ensureAudio()) return;

    const delay = Math.max(0, Number(delayMs || 0));
    const duration = Math.max(20, Number(durationMs || 120));
    const gainTarget = Math.min(0.4, Math.max(0.01, Number(gainValue || 0.12)));
    const startAt = audioCtx.currentTime + delay / 1000;
    const endAt = startAt + duration / 1000;

    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.value = Math.max(120, Number(freq || 880));
    gain.gain.setValueAtTime(0.0001, startAt);
    gain.gain.exponentialRampToValueAtTime(gainTarget, startAt + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, endAt);

    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start(startAt);
    osc.stop(endAt + 0.01);
  }

  function play(stageName) {
    if (!enabled) return false;

    switch (stageName) {
      case "mode_select":
        tone(740, 90, 0.08, 0);
        break;
      case "scan_start":
        tone(620, 80, 0.08, 0);
        tone(760, 100, 0.08, 110);
        break;
      case "capture_ok":
      case "scan_ok":
        tone(980, 80, 0.11, 0);
        tone(1180, 110, 0.11, 100);
        break;
      case "submit_start":
        tone(680, 110, 0.1, 0);
        tone(840, 130, 0.1, 130);
        break;
      case "warning":
        tone(420, 130, 0.09, 0);
        tone(420, 130, 0.09, 180);
        break;
      case "error":
        tone(520, 150, 0.11, 0);
        tone(420, 160, 0.11, 190);
        tone(320, 170, 0.11, 390);
        break;
      case "success":
        tone(740, 120, 0.11, 0);
        tone(980, 140, 0.11, 140);
        tone(1240, 170, 0.12, 320);
        break;
      default:
        tone(820, 90, 0.08, 0);
    }
    return true;
  }

  function setEnabled(next) {
    enabled = !!next;
    localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
    updateToggleLabels();
  }

  function isEnabled() {
    return !!enabled;
  }

  function updateToggleLabels() {
    document.querySelectorAll("[data-qa-sound-toggle]").forEach((btn) => {
      btn.textContent = enabled ? "🔊" : "🔇";
      btn.title = enabled ? "サウンド ON" : "サウンド OFF";
      btn.setAttribute("aria-label", enabled ? "サウンド ON" : "サウンド OFF");
    });
  }

  function ensureFabStyle() {
    if (document.getElementById("qa-sound-fab-style")) return;
    const style = document.createElement("style");
    style.id = "qa-sound-fab-style";
    style.textContent = `
      .qa-sound-fab {
        position: fixed;
        right: 16px;
        bottom: 16px;
        width: 48px;
        height: 48px;
        border-radius: 999px;
        border: 1px solid #d1d5db;
        background: #ffffff;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.18);
        z-index: 1100;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1.15rem;
        cursor: pointer;
        user-select: none;
      }
      .qa-sound-fab:hover {
        transform: translateY(-1px);
      }
      .qa-sound-fab:focus-visible {
        outline: 3px solid rgba(13, 110, 253, 0.3);
        outline-offset: 2px;
      }
    `;
    document.head.appendChild(style);
  }

  function ensureFloatingToggle() {
    if (document.querySelector(".qa-sound-fab[data-qa-sound-toggle]")) return;
    ensureFabStyle();
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "qa-sound-fab";
    btn.setAttribute("data-qa-sound-toggle", "1");
    document.body.appendChild(btn);
  }

  function bindToggle(selector) {
    ensureFloatingToggle();
    document.querySelectorAll(selector || "[data-qa-sound-toggle]").forEach((btn) => {
      if (btn.dataset.qaSoundBound === "1") return;
      btn.dataset.qaSoundBound = "1";
      btn.addEventListener("click", function () {
        setEnabled(!enabled);
        if (enabled) play("mode_select");
      });
    });
    updateToggleLabels();
  }

  function setupUnlockListeners() {
    const unlock = function () {
      ensureAudio();
      if (pendingSuccess) {
        pendingSuccess = false;
        play("success");
      }
    };
    document.addEventListener("click", unlock, { passive: true });
    document.addEventListener("keydown", unlock, { passive: true });
    document.addEventListener("touchstart", unlock, { passive: true });
  }

  function playSuccessWhenPossible() {
    if (!enabled) return;
    const ok = play("success");
    if (!ok || !unlocked) {
      pendingSuccess = true;
    }
  }

  setupUnlockListeners();
  windowObj.QAStageAudio = {
    play,
    setEnabled,
    isEnabled,
    bindToggle,
    playSuccessWhenPossible,
  };
})(window);
