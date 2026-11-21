(function (root) {
  "use strict";

  const POLL_INTERVAL_MS = 2200;
  const ZOOM_LABELS = {
    fit: "Tự khớp",
    fill: "Lấp đầy",
    "50": "50%",
    "75": "75%",
    "100": "100%",
    "125": "125%",
    "150": "150%",
  };

  // Curated fallback vector glyphs + brand colors for built-in Samsung/Android system apps
  const BUILTIN_APP_STYLES = [
    { match: /gallery|photos/i, bg: "#e11d48", svg: '<rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="9" cy="9" r="1.5"/><polyline points="20 15 15 10 5 20"/>' },
    { match: /camera/i, bg: "#dc2626", svg: '<path d="M21 18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3l2-3h4l2 3h3a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="3.5"/>' },
    { match: /dialer|telecom|incallui|phone/i, bg: "#16a34a", svg: '<path d="M20 16.5v2.5a2 2 0 0 1-2.18 2A17 17 0 0 1 4 7.18 2 2 0 0 1 6 5h2.5l1.5 4-2 1.5a13 13 0 0 0 5.5 5.5l1.5-2z"/>' },
    { match: /messaging|mms/i, bg: "#2563eb", svg: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' },
    { match: /settings/i, bg: "#475569", svg: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.09a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.09a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>' },
    { match: /contacts/i, bg: "#ea580c", svg: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>' },
    { match: /clock|alarm/i, bg: "#0284c7", svg: '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/>' },
    { match: /calendar/i, bg: "#0d9488", svg: '<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="16" y1="3" x2="16" y2="7"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="3" y1="10" x2="21" y2="10"/>' },
    { match: /notes|memo/i, bg: "#ca8a04", svg: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="13" y2="17"/>' },
    { match: /calculator|popupcalculator/i, bg: "#059669", svg: '<rect x="5" y="3" width="14" height="18" rx="2"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="12" x2="10" y2="12"/><line x1="14" y1="12" x2="16" y2="12"/><line x1="8" y1="16" x2="10" y2="16"/><line x1="14" y1="16" x2="16" y2="16"/>' },
    { match: /myfiles|documentsui|files/i, bg: "#d97706", svg: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>' },
    { match: /browser|sbrowser|chrome/i, bg: "#2563eb", svg: '<circle cx="12" cy="12" r="9"/><line x1="3" y1="12" x2="21" y2="12"/><path d="M12 3a14 14 0 0 1 4 9 14 14 0 0 1-4 9 14 14 0 0 1-4-9 14 14 0 0 1 4-9z"/>' },
    { match: /voicenote|recorder/i, bg: "#e11d48", svg: '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/>' },
    { match: /vending|galaxyapps|store/i, bg: "#0284c7", svg: '<path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/>' },
    { match: /lool|care|health/i, bg: "#10b981", svg: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>' },
  ];

  const PALETTE_SWATCHES = ["#0284c7", "#0d9488", "#2563eb", "#059669", "#d97706", "#dc2626", "#4f46e5", "#7c3aed"];

  function hashColor(str) {
    let h = 0;
    for (let i = 0; i < str.length; i += 1) h = (h * 31 + str.charCodeAt(i)) >>> 0;
    return PALETTE_SWATCHES[h % PALETTE_SWATCHES.length];
  }

  function initials(name) {
    const words = (name || "A").trim().split(/\s+/);
    if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
    return (words[0] || "A").slice(0, 2).toUpperCase();
  }

  function buildAppIconNode(doc, app) {
    const box = doc.createElement("div");
    box.className = "app-icon-box";
    if (app.icon) {
      box.style.background = "#0f172a";
      const img = doc.createElement("img");
      img.src = app.icon;
      img.alt = "";
      box.appendChild(img);
      return box;
    }
    const preset = BUILTIN_APP_STYLES.find((p) => p.match.test(app.package));
    if (preset) {
      box.style.background = preset.bg;
      box.innerHTML = `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${preset.svg}</svg>`;
      return box;
    }
    box.style.background = hashColor(app.package || app.name);
    box.textContent = initials(app.name);
    return box;
  }

  function createController(doc, getApi, layoutLib) {
    const layoutEngine = layoutLib || root.PhoneControlLayout;

    const state = {
      devices: [],
      selectedId: null,
      settings: {
        quality: "balanced",
        turn_screen_off: false,
        stay_awake: true,
        always_on_top: false,
        enable_audio: true,
        auto_mirror_saved: false,
        swipe_step: "medium",
        zoom_mode: "fit",
        sidebar_collapsed: false,
        embedded_workspace: true,
      },
      tools: null,
      phoneOnlyMode: false,
      demoCount: 0,
      activeDrawer: null, // null | "add" | "apps" | "diag" | "rename"
      renamingDeviceId: null,
      installedApps: [],
      appFilter: "all", // all | user
      appsSerialLoaded: null,
      iconMap: {},
      iconFetching: false,
      diagnostics: null,
      lastScreenshotPath: "",
      pollTimer: null,
      resizeObserver: null,
      syncRaf: null,
      scanning: false,
    };

    const el = {
      appShell: doc.getElementById("appShell"),
      miniStrip: doc.getElementById("miniStrip"),
      btnExitPhoneOnly: doc.getElementById("btnExitPhoneOnly"),
      miniStripDeviceName: doc.getElementById("miniStripDeviceName"),
      btnMiniScreenOff: doc.getElementById("btnMiniScreenOff"),
      btnMiniAlwaysOnTop: doc.getElementById("btnMiniAlwaysOnTop"),
      btnMiniRotate: doc.getElementById("btnMiniRotate"),
      btnMiniScreenshot: doc.getElementById("btnMiniScreenshot"),

      btnToggleSidebar: doc.getElementById("btnToggleSidebar"),
      controlSidebar: doc.getElementById("controlSidebar"),
      toolStatusText: doc.getElementById("toolStatusText"),
      selectDemoCount: doc.getElementById("selectDemoCount"),
      btnAlwaysOnTop: doc.getElementById("btnAlwaysOnTop"),
      btnTopScreenOff: doc.getElementById("btnTopScreenOff"),
      topScreenOffLabel: doc.getElementById("topScreenOffLabel"),
      btnOpenDiagDrawer: doc.getElementById("btnOpenDiagDrawer"),
      btnPhoneOnly: doc.getElementById("btnPhoneOnly"),
      btnOpenAddDrawer: doc.getElementById("btnOpenAddDrawer"),
      btnToggleFullscreen: doc.getElementById("btnToggleFullscreen"),

      btnRefresh: doc.getElementById("btnRefresh"),
      btnMirrorAll: doc.getElementById("btnMirrorAll"),
      deviceList: doc.getElementById("deviceList"),
      chkAutoMirrorAll: doc.getElementById("chkAutoMirrorAll"),
      btnSwitchWifi: doc.getElementById("btnSwitchWifi"),

      selectedDeviceBadge: doc.getElementById("selectedDeviceBadge"),
      btnToggleMirror: doc.getElementById("btnToggleMirror"),
      mirrorBtnLabel: doc.getElementById("mirrorBtnLabel"),
      btnScreenshot: doc.getElementById("btnScreenshot"),
      btnToggleScreenOff: doc.getElementById("btnToggleScreenOff"),
      sidebarScreenOffLabel: doc.getElementById("sidebarScreenOffLabel"),
      btnToggleTouchDot: doc.getElementById("btnToggleTouchDot"),
      btnSideAlwaysOnTop: doc.getElementById("btnSideAlwaysOnTop"),
      chkTurnScreenOff: doc.getElementById("chkTurnScreenOff"),
      chkStayAwake: doc.getElementById("chkStayAwake"),
      chkEnableAudio: doc.getElementById("chkEnableAudio"),

      btnOpenAppsDrawer: doc.getElementById("btnOpenAppsDrawer"),
      btnSideDiagDrawer: doc.getElementById("btnSideDiagDrawer"),
      btnRotate: doc.getElementById("btnRotate"),
      btnSendFile: doc.getElementById("btnSendFile"),
      btnOpenScreenshots: doc.getElementById("btnOpenScreenshots"),

      drawerAddDevice: doc.getElementById("drawerAddDevice"),
      drawerApps: doc.getElementById("drawerApps"),
      drawerDiagnostics: doc.getElementById("drawerDiagnostics"),
      drawerRename: doc.getElementById("drawerRename"),
      inputWifiAddr: doc.getElementById("inputWifiAddr"),
      btnDoWifiConnect: doc.getElementById("btnDoWifiConnect"),
      inputPairAddr: doc.getElementById("inputPairAddr"),
      inputPairCode: doc.getElementById("inputPairCode"),
      inputConnectAfterPair: doc.getElementById("inputConnectAfterPair"),
      btnDoWifiPair: doc.getElementById("btnDoWifiPair"),
      inputSearchApps: doc.getElementById("inputSearchApps"),
      btnReloadApps: doc.getElementById("btnReloadApps"),
      appPickerList: doc.getElementById("appPickerList"),
      btnReloadDiag: doc.getElementById("btnReloadDiag"),
      diagBody: doc.getElementById("diagBody"),
      inputDeviceNickname: doc.getElementById("inputDeviceNickname"),
      btnSaveRename: doc.getElementById("btnSaveRename"),

      workspaceStage: doc.getElementById("workspaceStage"),
      stageEmpty: doc.getElementById("stageEmpty"),
      stageGrid: doc.getElementById("stageGrid"),
      btnEmptyStartMirror: doc.getElementById("btnEmptyStartMirror"),
      btnEmptyDemo4: doc.getElementById("btnEmptyDemo4"),

      statusBar: doc.getElementById("statusBar"),
      statusMessage: doc.getElementById("statusMessage"),
      btnStatusAction: doc.getElementById("btnStatusAction"),
      layoutSummaryText: doc.getElementById("layoutSummaryText"),
    };

    const zoomButtons = Array.from(doc.querySelectorAll(".zoom-btn[data-zoom]"));
    const qualityButtons = Array.from(doc.querySelectorAll(".seg-btn[data-quality]"));
    const stepButtons = Array.from(doc.querySelectorAll(".step-btn[data-step]"));
    const swipeButtons = Array.from(doc.querySelectorAll("[data-swipe]"));
    const actionButtons = Array.from(doc.querySelectorAll("[data-action]"));
    const quickAppButtons = Array.from(doc.querySelectorAll("[data-app]"));
    const tabButtons = Array.from(doc.querySelectorAll("#drawerAddDevice .seg-btn[data-tab]"));
    const appFilterButtons = Array.from(doc.querySelectorAll("#drawerApps .seg-btn[data-app-filter]"));
    const closeDrawerButtons = Array.from(doc.querySelectorAll("[data-close-drawer]"));

    let statusActionHandler = null;

    function setStatus(message, tone = "neutral", actionLabel = "", onAction = null) {
      el.statusMessage.textContent = message;
      el.statusBar.className = "statusbar" + (tone === "error" ? " error" : tone === "success" ? " success" : "");
      statusActionHandler = onAction;
      if (actionLabel && onAction) {
        el.btnStatusAction.textContent = actionLabel;
        el.btnStatusAction.classList.remove("hidden");
      } else {
        el.btnStatusAction.classList.add("hidden");
      }
    }

    function getSelectedDevice() {
      if (!state.selectedId) return null;
      return state.devices.find((d) => d.id === state.selectedId) || null;
    }

    function ensureValidSelection() {
      if (getSelectedDevice()) return;
      const firstMirror = state.devices.find((d) => d.online && d.mirroring);
      const firstOnline = state.devices.find((d) => d.online);
      const fallback = firstMirror || firstOnline || state.devices[0] || null;
      state.selectedId = fallback ? fallback.id : null;
    }

    async function callApi(method, ...args) {
      const api = getApi();
      if (!api || typeof api[method] !== "function") {
        return { ok: false, error: "Chưa kết nối tới backend Python." };
      }
      return api[method](...args);
    }

    function applySidebarState() {
      const collapsed = Boolean(state.settings.sidebar_collapsed);
      el.controlSidebar.classList.toggle("collapsed", collapsed);
      el.btnToggleSidebar.setAttribute("aria-expanded", collapsed ? "false" : "true");
    }

    function applyPhoneOnlyState() {
      el.appShell.classList.toggle("phone-only", state.phoneOnlyMode);
      el.miniStrip.classList.toggle("hidden", !state.phoneOnlyMode);
      renderWorkspaceStage();
    }

    function renderAlwaysOnTopState() {
      const pinned = Boolean(state.settings.always_on_top);
      el.btnAlwaysOnTop.classList.toggle("active", pinned);
      el.btnAlwaysOnTop.setAttribute("aria-pressed", pinned ? "true" : "false");
      el.btnSideAlwaysOnTop.classList.toggle("active", pinned);
      el.btnSideAlwaysOnTop.setAttribute("aria-pressed", pinned ? "true" : "false");
      el.btnMiniAlwaysOnTop.classList.toggle("active", pinned);
      el.btnMiniAlwaysOnTop.setAttribute("aria-pressed", pinned ? "true" : "false");
    }

    function renderToolStatus() {
      if (!state.tools) return;
      if (state.tools.adb_available && state.tools.scrcpy_available) {
        const online = state.devices.filter((d) => d.online).length;
        const mirroring = state.devices.filter((d) => d.mirroring).length;
        el.toolStatusText.textContent = online > 0
          ? `${online} máy kết nối • ${mirroring} đang chiếu`
          : "Sẵn sàng • Chờ kết nối máy";
      } else {
        el.toolStatusText.textContent = "Thiếu adb hoặc scrcpy";
      }
    }

    function renderSettings() {
      const s = state.settings;
      el.chkAutoMirrorAll.checked = Boolean(s.auto_mirror_saved);
      el.chkTurnScreenOff.checked = Boolean(s.turn_screen_off);
      el.chkStayAwake.checked = Boolean(s.stay_awake);
      el.chkEnableAudio.checked = Boolean(s.enable_audio);

      for (const btn of qualityButtons) {
        btn.classList.toggle("active", btn.dataset.quality === s.quality);
      }
      for (const btn of stepButtons) {
        btn.classList.toggle("active", btn.dataset.step === s.swipe_step);
      }
      for (const btn of zoomButtons) {
        btn.classList.toggle("active", btn.dataset.zoom === String(s.zoom_mode));
      }
      applySidebarState();
      renderAlwaysOnTopState();
    }

    function buildDeviceMeta(dev) {
      if (dev.state === "unauthorized") return "Bấm 'Cho phép' trên màn hình ĐT";
      if (dev.state === "authorizing") return "Đang xác thực ADB...";
      if (!dev.online) {
        return dev.wifi_ip ? `Chưa cắm • IP ${dev.wifi_ip}` : "Đã lưu • Cắm cáp để kết nối";
      }
      const bits = [];
      if (dev.android_version) bits.push(`Android ${dev.android_version}`);
      if (typeof dev.battery === "number") bits.push(`${dev.battery}%`);
      if (dev.orientation === 1 || dev.orientation === 3) bits.push("Ngang");
      if (dev.wifi_ip) bits.push(dev.wifi_ip);
      return bits.join(" • ") || dev.serial;
    }

    function renderDevices() {
      ensureValidSelection();
      renderToolStatus();
      el.deviceList.innerHTML = "";

      const onlineCount = state.devices.filter((d) => d.online).length;
      el.btnMirrorAll.disabled = onlineCount === 0;

      if (state.devices.length === 0) {
        const empty = doc.createElement("div");
        empty.className = "empty-inline";
        empty.textContent = "Chưa thấy điện thoại nào. Cắm cáp USB hoặc bấm '+ Thêm máy'.";
        el.deviceList.appendChild(empty);
        renderControlStates();
        renderWorkspaceStage();
        return;
      }

      for (const dev of state.devices) {
        const row = doc.createElement("div");
        row.className = "device-item" + (dev.id === state.selectedId ? " selected" : "");
        row.setAttribute("role", "option");
        row.setAttribute("aria-selected", dev.id === state.selectedId ? "true" : "false");
        row.dataset.deviceId = dev.id;

        const main = doc.createElement("div");
        main.className = "device-item-main";

        const dot = doc.createElement("span");
        dot.className = "status-dot" + (dev.online ? " online" : dev.state === "unauthorized" || dev.state === "authorizing" ? " warn" : "");
        main.appendChild(dot);

        const textWrap = doc.createElement("div");
        textWrap.className = "device-item-text";

        const titleRow = doc.createElement("div");
        titleRow.className = "device-item-title-row";

        const nameSpan = doc.createElement("span");
        nameSpan.className = "device-item-name";
        nameSpan.textContent = dev.display_name || dev.serial;
        titleRow.appendChild(nameSpan);

        if (dev.online) {
          const tTag = doc.createElement("span");
          tTag.className = "tag " + (dev.transport === "wifi" ? "wifi" : "usb");
          tTag.textContent = dev.transport === "wifi" ? "Wi-Fi" : "USB";
          titleRow.appendChild(tTag);
        }
        if (dev.mirroring) {
          const lTag = doc.createElement("span");
          lTag.className = "tag live";
          lTag.textContent = "Chiếu";
          titleRow.appendChild(lTag);
        }

        const meta = doc.createElement("div");
        meta.className = "device-item-meta";
        meta.textContent = buildDeviceMeta(dev);

        textWrap.appendChild(titleRow);
        textWrap.appendChild(meta);
        main.appendChild(textWrap);
        row.appendChild(main);

        const actions = doc.createElement("div");
        actions.className = "device-item-actions";

        if (dev.online) {
          const mirrorQuickBtn = doc.createElement("button");
          mirrorQuickBtn.type = "button";
          mirrorQuickBtn.className = "btn-outline xs";
          mirrorQuickBtn.textContent = dev.mirroring ? "Dừng" : "Mở";
          mirrorQuickBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            state.selectedId = dev.id;
            toggleMirrorForDevice(dev);
          });
          actions.appendChild(mirrorQuickBtn);
        } else if (dev.wifi_ip) {
          const wifiBtn = doc.createElement("button");
          wifiBtn.type = "button";
          wifiBtn.className = "btn-outline xs";
          wifiBtn.textContent = "Wi-Fi";
          wifiBtn.title = `Kết nối lại ${dev.wifi_ip}:5555`;
          wifiBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            handleReconnectSavedWifi(dev);
          });
          actions.appendChild(wifiBtn);
        }

        if (dev.saved) {
          const editBtn = doc.createElement("button");
          editBtn.type = "button";
          editBtn.className = "icon-btn mini";
          editBtn.title = "Đặt tên gợi nhớ";
          editBtn.setAttribute("aria-label", `Đổi tên ${dev.display_name}`);
          editBtn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>';
          editBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            openRenameDrawer(dev);
          });
          actions.appendChild(editBtn);

          if (!dev.online) {
            const delBtn = doc.createElement("button");
            delBtn.type = "button";
            delBtn.className = "icon-btn mini danger";
            delBtn.title = "Xóa khỏi danh sách đã lưu";
            delBtn.setAttribute("aria-label", `Xóa ${dev.display_name}`);
            delBtn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path></svg>';
            delBtn.addEventListener("click", (evt) => {
              evt.stopPropagation();
              handleDeleteSaved(dev);
            });
            actions.appendChild(delBtn);
          }
        }

        row.appendChild(actions);
        row.addEventListener("click", () => {
          state.selectedId = dev.id;
          renderDevices();
        });
        el.deviceList.appendChild(row);
      }

      renderControlStates();
      renderWorkspaceStage();
    }

    function renderControlStates() {
      const dev = getSelectedDevice();
      const canControl = Boolean(dev && dev.online);

      if (!dev) {
        el.selectedDeviceBadge.textContent = "Chưa chọn máy";
        el.selectedDeviceBadge.className = "device-pill";
        el.miniStripDeviceName.textContent = "Phone Control";
      } else if (dev.online) {
        el.selectedDeviceBadge.textContent = dev.display_name;
        el.selectedDeviceBadge.className = "device-pill online";
        el.miniStripDeviceName.textContent = dev.display_name;
      } else {
        el.selectedDeviceBadge.textContent = `${dev.display_name} (chưa cắm)`;
        el.selectedDeviceBadge.className = "device-pill";
        el.miniStripDeviceName.textContent = dev.display_name;
      }

      el.btnToggleMirror.disabled = !canControl;
      el.btnEmptyStartMirror.disabled = !canControl;
      el.btnScreenshot.disabled = !canControl;
      el.btnMiniScreenshot.disabled = !canControl;
      el.btnMiniRotate.disabled = !canControl;
      el.btnToggleScreenOff.disabled = !canControl;
      el.btnTopScreenOff.disabled = !canControl;
      el.btnMiniScreenOff.disabled = !canControl;
      el.btnToggleTouchDot.disabled = !canControl;
      el.btnOpenAppsDrawer.disabled = !canControl;
      el.btnOpenDiagDrawer.disabled = !canControl;
      el.btnSideDiagDrawer.disabled = !canControl;
      el.btnSendFile.disabled = !canControl;
      el.btnSwitchWifi.disabled = !(canControl && dev.transport === "usb");

      // Lit UI states for toggle buttons
      const screenOff = Boolean(dev && dev.screen_off);
      const offLabel = screenOff ? "Màn ĐT: Tắt" : "Tắt màn ĐT";
      el.sidebarScreenOffLabel.textContent = offLabel;
      el.topScreenOffLabel.textContent = offLabel;
      el.btnMiniScreenOff.textContent = offLabel;
      for (const b of [el.btnToggleScreenOff, el.btnTopScreenOff, el.btnMiniScreenOff]) {
        b.classList.toggle("active-amber", screenOff);
        b.setAttribute("aria-pressed", screenOff ? "true" : "false");
      }

      const touchOn = Boolean(dev && dev.show_touches);
      el.btnToggleTouchDot.classList.toggle("active", touchOn);
      el.btnToggleTouchDot.setAttribute("aria-pressed", touchOn ? "true" : "false");

      const isLandscape = Boolean(dev && (dev.orientation === 1 || dev.orientation === 3));
      el.btnRotate.classList.toggle("active", isLandscape);
      el.btnRotate.setAttribute("aria-pressed", isLandscape ? "true" : "false");

      if (dev && dev.mirroring) {
        el.btnToggleMirror.classList.add("stop-mode");
        el.mirrorBtnLabel.textContent = "Dừng chiếu";
      } else {
        el.btnToggleMirror.classList.remove("stop-mode");
        el.mirrorBtnLabel.textContent = "Mở màn hình";
      }

      for (const btn of swipeButtons) btn.disabled = !canControl;
      for (const btn of actionButtons) btn.disabled = !canControl;
      for (const btn of quickAppButtons) btn.disabled = !canControl;
    }

    function getWorkspaceItems() {
      if (state.demoCount > 0) {
        const demos = [];
        const models = ["Galaxy Note20 Ultra", "Galaxy S10 5G", "Galaxy S24 Ultra", "Pixel 9 Pro", "Galaxy A55", "Xiaomi 14"];
        for (let i = 0; i < state.demoCount; i += 1) {
          demos.push({
            id: `DEMO_${i + 1}`,
            serial: `DEMO_${i + 1}`,
            display_name: models[i % models.length],
            battery: 92 - i * 7,
            screen_width: 1080,
            screen_height: 2340,
            demo: true,
          });
        }
        return demos;
      }
      return state.devices.filter((d) => d.online && d.mirroring);
    }

    function renderWorkspaceStage() {
      const items = getWorkspaceItems();
      const stageRect = el.workspaceStage.getBoundingClientRect();
      const stageW = Math.max(320, stageRect.width || 780);
      const stageH = Math.max(320, stageRect.height || 720);
      const zoomMode = String(state.settings.zoom_mode || "fit");
      const zoomLabel = ZOOM_LABELS[zoomMode] || zoomMode;

      if (items.length === 0) {
        el.stageEmpty.classList.remove("hidden");
        el.stageGrid.classList.add("hidden");
        el.stageGrid.innerHTML = "";
        el.workspaceStage.classList.remove("scrollable");
        el.layoutSummaryText.textContent = `Bố cục: ${zoomLabel}`;
        callApi("sync_mirror_slots", []);
        return;
      }

      el.stageEmpty.classList.add("hidden");
      el.stageGrid.classList.remove("hidden");

      const plan = layoutEngine.computeWorkspaceLayout(stageW, stageH, items, zoomMode);
      el.workspaceStage.classList.toggle("scrollable", Boolean(plan.scrollable));
      el.stageGrid.style.gridTemplateColumns = `repeat(${plan.cols}, auto)`;
      el.stageGrid.style.gap = `${plan.gap}px`;
      el.stageGrid.style.padding = `${plan.padding}px`;
      el.stageGrid.innerHTML = "";

      const demoTag = state.demoCount > 0 ? " (Demo)" : "";
      el.layoutSummaryText.textContent = `${items.length} khung${demoTag} • Lưới ${plan.cols}×${plan.rows} • ${zoomLabel}`;

      const nowStr = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });

      items.forEach((item, idx) => {
        const slotGeom = plan.slots[idx];
        const card = doc.createElement("div");
        card.className = "phone-slot" + (!item.demo && item.id === state.selectedId ? " selected" : "");
        card.dataset.slotSerial = item.serial;
        card.dataset.landscape = slotGeom.landscape ? "true" : "false";
        card.style.width = `${slotGeom.cardWidth}px`;
        card.style.height = `${slotGeom.cardHeight}px`;

        const head = doc.createElement("div");
        head.className = "phone-slot-head";

        const titleWrap = doc.createElement("div");
        titleWrap.className = "phone-slot-title";

        const dot = doc.createElement("span");
        dot.className = "status-dot online";
        titleWrap.appendChild(dot);

        const nameEl = doc.createElement("span");
        nameEl.className = "phone-slot-name";
        nameEl.textContent = item.display_name || item.serial;
        titleWrap.appendChild(nameEl);

        if (typeof item.battery === "number") {
          const batEl = doc.createElement("span");
          batEl.className = "phone-slot-meta";
          batEl.textContent = `${item.battery}%`;
          titleWrap.appendChild(batEl);
        }

        const tools = doc.createElement("div");
        tools.className = "phone-slot-tools";

        if (!item.demo) {
          const offBtn = doc.createElement("button");
          offBtn.type = "button";
          offBtn.className = "icon-btn mini" + (item.screen_off ? " active-amber" : "");
          offBtn.title = item.screen_off ? "Bật sáng lại màn hình máy này" : "Tắt màn hình vật lý máy này";
          offBtn.setAttribute("aria-label", `Tắt hoặc bật màn hình ${item.display_name}`);
          offBtn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';
          offBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            toggleDisplayPowerFor(item);
          });
          tools.appendChild(offBtn);

          const shotBtn = doc.createElement("button");
          shotBtn.type = "button";
          shotBtn.className = "icon-btn mini";
          shotBtn.title = "Chụp ảnh màn hình máy này";
          shotBtn.setAttribute("aria-label", `Chụp ảnh ${item.display_name}`);
          shotBtn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="3.5"></circle></svg>';
          shotBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            handleScreenshotFor(item);
          });
          tools.appendChild(shotBtn);

          const closeBtn = doc.createElement("button");
          closeBtn.type = "button";
          closeBtn.className = "icon-btn mini danger";
          closeBtn.title = "Đóng khung chiếu máy này";
          closeBtn.setAttribute("aria-label", `Đóng ${item.display_name}`);
          closeBtn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
          closeBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            stopMirrorForDevice(item);
          });
          tools.appendChild(closeBtn);
        } else {
          const scaleSpan = doc.createElement("span");
          scaleSpan.className = "phone-slot-meta";
          scaleSpan.textContent = `${slotGeom.scalePct}%`;
          tools.appendChild(scaleSpan);
        }

        head.appendChild(titleWrap);
        head.appendChild(tools);
        head.addEventListener("click", () => {
          if (!item.demo) {
            state.selectedId = item.id;
            renderDevices();
          }
        });

        const viewport = doc.createElement("div");
        viewport.className = "phone-slot-viewport";
        viewport.dataset.viewportSerial = item.serial;
        viewport.style.width = `${slotGeom.videoWidth}px`;
        viewport.style.height = `${slotGeom.videoHeight}px`;

        if (item.demo) {
          viewport.innerHTML = `
            <div class="demo-screen">
              <div class="demo-statusbar">
                <span>${nowStr}</span>
                <span>5G • ${item.battery}%</span>
              </div>
              <div class="demo-center">
                <div class="demo-clock">${nowStr}</div>
                <div class="demo-badge">${slotGeom.videoWidth}×${slotGeom.videoHeight}px • ${slotGeom.scalePct}%</div>
              </div>
              <div class="demo-apps">
                <div class="demo-app-dot"></div>
                <div class="demo-app-dot"></div>
                <div class="demo-app-dot"></div>
                <div class="demo-app-dot"></div>
              </div>
            </div>
          `;
        } else {
          viewport.textContent = "Đang đồng bộ màn hình scrcpy...";
        }

        card.appendChild(head);
        card.appendChild(viewport);
        el.stageGrid.appendChild(card);
      });

      syncNativeOverlaySlots();
    }

    function syncNativeOverlaySlots() {
      if (state.demoCount > 0) {
        callApi("sync_mirror_slots", []);
        return;
      }
      const dpr = root.devicePixelRatio || 1;
      const stageRect = el.workspaceStage.getBoundingClientRect();
      const viewports = Array.from(el.stageGrid.querySelectorAll(".phone-slot-viewport[data-viewport-serial]"));
      const slots = viewports.map((vp) => {
        const r = vp.getBoundingClientRect();
        const visible =
          r.width >= 40 &&
          r.height >= 40 &&
          r.bottom > stageRect.top + 4 &&
          r.top < stageRect.bottom - 4 &&
          r.right > stageRect.left + 4 &&
          r.left < stageRect.right - 4;
        return {
          serial: vp.dataset.viewportSerial,
          x: Math.round(r.left * dpr),
          y: Math.round(r.top * dpr),
          width: Math.round(r.width * dpr),
          height: Math.round(r.height * dpr),
          visible,
        };
      });
      callApi("sync_mirror_slots", slots);
    }

    function scheduleStageRender() {
      if (state.syncRaf) return;
      state.syncRaf = requestAnimationFrame(() => {
        state.syncRaf = null;
        renderWorkspaceStage();
      });
    }

    // Inline Sidebar Drawers
    function openDrawer(name) {
      if (state.phoneOnlyMode) {
        state.phoneOnlyMode = false;
        applyPhoneOnlyState();
      }
      if (state.settings.sidebar_collapsed) {
        state.settings.sidebar_collapsed = false;
        applySidebarState();
        renderWorkspaceStage();
      }
      state.activeDrawer = name;
      el.drawerAddDevice.classList.toggle("hidden", name !== "add");
      el.drawerApps.classList.toggle("hidden", name !== "apps");
      el.drawerDiagnostics.classList.toggle("hidden", name !== "diag");
      el.drawerRename.classList.toggle("hidden", name !== "rename");
    }

    function closeDrawers() {
      state.activeDrawer = null;
      state.renamingDeviceId = null;
      el.drawerAddDevice.classList.add("hidden");
      el.drawerApps.classList.add("hidden");
      el.drawerDiagnostics.classList.add("hidden");
      el.drawerRename.classList.add("hidden");
    }

    function openRenameDrawer(dev) {
      state.renamingDeviceId = dev.id;
      el.inputDeviceNickname.value = dev.nickname || dev.display_name || "";
      openDrawer("rename");
      el.inputDeviceNickname.focus();
      el.inputDeviceNickname.select();
    }

    // Phone-Style Icon Grid App Drawer
    async function openAppsDrawer(forceRefresh = false) {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      openDrawer("apps");
      el.inputSearchApps.value = "";
      if (!forceRefresh && state.appsSerialLoaded === dev.serial && state.installedApps.length > 0) {
        renderAppsGrid("");
        el.inputSearchApps.focus();
        return;
      }
      el.appPickerList.innerHTML = '<div class="empty-inline">Đang tải danh sách ứng dụng từ điện thoại...</div>';
      const res = await callApi("list_apps", dev.serial, forceRefresh);
      if (!res.ok) {
        el.appPickerList.innerHTML = `<div class="empty-inline">${res.error || "Không tải được danh sách app."}</div>`;
        return;
      }
      state.installedApps = res.data.apps || [];
      state.appsSerialLoaded = dev.serial;
      for (const a of state.installedApps) {
        if (a.icon) state.iconMap[a.package] = a.icon;
      }
      renderAppsGrid("");
      el.inputSearchApps.focus();
      loadMissingIconsInBackground();
    }

    async function loadMissingIconsInBackground() {
      if (state.iconFetching) return;
      const missing = state.installedApps
        .filter((a) => !a.icon && !state.iconMap[a.package] && !BUILTIN_APP_STYLES.some((p) => p.match.test(a.package)))
        .map((a) => a.package);
      if (missing.length === 0) return;

      state.iconFetching = true;
      try {
        // Fetch in small batches so icons appear progressively without stalling UI
        for (let i = 0; i < missing.length; i += 24) {
          const chunk = missing.slice(i, i + 24);
          const res = await callApi("fetch_app_icons", chunk);
          if (res.ok && res.data && res.data.icons) {
            const icons = res.data.icons;
            let updated = false;
            for (const pkg of Object.keys(icons)) {
              state.iconMap[pkg] = icons[pkg];
              updated = true;
            }
            if (updated && state.activeDrawer === "apps") {
              for (const app of state.installedApps) {
                if (state.iconMap[app.package]) app.icon = state.iconMap[app.package];
              }
              renderAppsGrid(el.inputSearchApps.value);
            }
          }
        }
      } finally {
        state.iconFetching = false;
      }
    }

    function renderAppsGrid(query) {
      const q = (query || "").trim().toLowerCase();
      let list = state.installedApps;
      if (state.appFilter === "user") {
        list = list.filter((a) => !a.system);
      }
      if (q) {
        list = list.filter((a) => a.name.toLowerCase().includes(q) || a.package.toLowerCase().includes(q));
      }

      el.appPickerList.innerHTML = "";
      if (list.length === 0) {
        el.appPickerList.innerHTML = '<div class="empty-inline">Không tìm thấy ứng dụng phù hợp.</div>';
        return;
      }

      const dev = getSelectedDevice();
      const grid = doc.createElement("div");
      grid.className = "app-icon-grid";

      for (const app of list) {
        const tile = doc.createElement("button");
        tile.type = "button";
        tile.className = "app-tile";
        tile.title = `${app.name} (${app.package})`;

        const iconObj = Object.assign({}, app, { icon: app.icon || state.iconMap[app.package] || "" });
        tile.appendChild(buildAppIconNode(doc, iconObj));

        const lbl = doc.createElement("span");
        lbl.className = "app-tile-label";
        lbl.textContent = app.name;
        tile.appendChild(lbl);

        tile.addEventListener("click", async () => {
          if (!dev || !dev.online) return;
          setStatus(`Đang mở ${app.name}...`, "neutral");
          const res = await callApi("launch_package", dev.serial, app.package);
          if (!res.ok) {
            setStatus(res.error || `Không mở được ${app.name}.`, "error");
          } else {
            setStatus(`Đã mở ${app.name}.`, "success");
          }
        });
        grid.appendChild(tile);
      }
      el.appPickerList.appendChild(grid);
    }

    // Diagnostics & Health Drawer
    async function openDiagnosticsDrawer() {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      openDrawer("diag");
      el.diagBody.innerHTML = '<div class="empty-inline">Đang đo pin, RAM, sóng Wi-Fi và kiểm tra lỗi ứng dụng...</div>';
      const res = await callApi("get_diagnostics", dev.serial);
      if (!res.ok) {
        el.diagBody.innerHTML = `<div class="empty-inline">${res.error || "Không đọc được chẩn đoán máy."}</div>`;
        return;
      }
      state.diagnostics = res.data;
      dev.pointer_location = Boolean(res.data.pointer_location);
      renderDiagnosticsPanel(dev, res.data);
    }

    function renderDiagnosticsPanel(dev, diag) {
      el.diagBody.innerHTML = "";
      const bat = diag.battery || {};
      const mem = diag.memory || {};
      const sto = diag.storage || {};
      const wifi = diag.wifi || {};

      // 1. Battery & Performance block
      const batBlock = doc.createElement("div");
      batBlock.className = "diag-block";
      const tempWarn = typeof bat.temperature_c === "number" && bat.temperature_c >= 40;
      const healthGood = bat.health_code === 2;
      batBlock.innerHTML = `
        <div class="diag-block-title">Pin &amp; Hiệu năng</div>
        <div class="diag-grid-2">
          <div class="diag-stat">
            <span class="diag-stat-label">Mức pin • Trạng thái</span>
            <span class="diag-stat-val">${bat.level != null ? bat.level + "%" : "—"} • ${bat.status_label || "—"}</span>
          </div>
          <div class="diag-stat">
            <span class="diag-stat-label">Nhiệt độ • Điện áp</span>
            <span class="diag-stat-val ${tempWarn ? "warn" : ""}">${bat.temperature_c != null ? bat.temperature_c + "°C" : "—"} • ${bat.voltage_v != null ? bat.voltage_v + "V" : "—"}</span>
          </div>
          <div class="diag-stat">
            <span class="diag-stat-label">Sức khỏe pin</span>
            <span class="diag-stat-val ${healthGood ? "good" : "warn"}">${bat.health_label || "—"}</span>
          </div>
          <div class="diag-stat">
            <span class="diag-stat-label">Công nghệ</span>
            <span class="diag-stat-val">${bat.technology || "Li-ion"}</span>
          </div>
        </div>
        <div class="meter-row">
          <div class="meter-head"><span>RAM đang dùng</span><span>${mem.used_gb != null ? `${mem.used_gb} / ${mem.total_gb} GB (${mem.used_pct}%)` : "—"}</span></div>
          <div class="meter-track"><div class="meter-fill ${(mem.used_pct || 0) >= 85 ? "warn" : ""}" style="width:${mem.used_pct || 0}%"></div></div>
        </div>
        <div class="meter-row">
          <div class="meter-head"><span>Bộ nhớ trong</span><span>${sto.used_gb != null ? `${sto.used_gb} / ${sto.total_gb} GB (${sto.used_pct}%)` : "—"}</span></div>
          <div class="meter-track"><div class="meter-fill ${(sto.used_pct || 0) >= 85 ? "warn" : ""}" style="width:${sto.used_pct || 0}%"></div></div>
        </div>
      `;
      const perfBtns = doc.createElement("div");
      perfBtns.className = "btn-row-2";

      const saverBtn = doc.createElement("button");
      saverBtn.type = "button";
      saverBtn.className = "ctrl-btn" + (diag.power_save ? " active-amber" : "");
      saverBtn.id = "btnDiagBatterySaver";
      saverBtn.textContent = diag.power_save ? "Tiết kiệm pin: Bật" : "Tiết kiệm pin";
      saverBtn.addEventListener("click", async () => {
        const next = !diag.power_save;
        const r = await callApi("set_battery_saver", dev.serial, next);
        if (r.ok) {
          diag.power_save = next;
          renderDiagnosticsPanel(dev, diag);
          setStatus(next ? "Đã bật chế độ Tiết kiệm pin." : "Đã tắt chế độ Tiết kiệm pin.", "success");
        } else {
          setStatus(r.error || "Không đổi được tiết kiệm pin.", "error");
        }
      });

      const cleanBtn = doc.createElement("button");
      cleanBtn.type = "button";
      cleanBtn.className = "ctrl-btn";
      cleanBtn.id = "btnDiagClearBg";
      cleanBtn.textContent = "Dọn app chạy nền";
      cleanBtn.addEventListener("click", async () => {
        const r = await callApi("clear_background_processes", dev.serial);
        if (r.ok) {
          setStatus("Đã dọn các tiến trình chạy nền để giải phóng RAM.", "success");
          openDiagnosticsDrawer();
        } else {
          setStatus(r.error || "Không dọn được tiến trình nền.", "error");
        }
      });

      perfBtns.appendChild(saverBtn);
      perfBtns.appendChild(cleanBtn);
      batBlock.appendChild(perfBtns);
      el.diagBody.appendChild(batBlock);

      // 2. Screen & Touch Fault Diagnostics
      const touchBlock = doc.createElement("div");
      touchBlock.className = "diag-block";
      touchBlock.innerHTML = `<div class="diag-block-title">Kiểm tra màn hình &amp; Cảm ứng lỗi</div>`;
      const touchBtns = doc.createElement("div");
      touchBtns.className = "btn-row-2";

      const ptrBtn = doc.createElement("button");
      ptrBtn.type = "button";
      ptrBtn.id = "btnDiagPointerGrid";
      ptrBtn.className = "ctrl-btn" + (diag.pointer_location ? " active" : "");
      ptrBtn.textContent = diag.pointer_location ? "Lưới cảm ứng: Bật" : "Lưới test cảm ứng";
      ptrBtn.title = "Vẽ đường tọa độ X/Y trên màn hình để kiểm tra điểm chết / loạn cảm ứng";
      ptrBtn.addEventListener("click", async () => {
        const next = !diag.pointer_location;
        const r = await callApi("set_pointer_location", dev.serial, next);
        if (r.ok) {
          diag.pointer_location = next;
          dev.pointer_location = next;
          renderDiagnosticsPanel(dev, diag);
          setStatus(next ? "Đã bật lưới vẽ test cảm ứng trên điện thoại." : "Đã tắt lưới test cảm ứng.", "success");
        } else {
          setStatus(r.error || "Không bật được lưới cảm ứng.", "error");
        }
      });
      touchBtns.appendChild(ptrBtn);

      const hwBtn = doc.createElement("button");
      hwBtn.type = "button";
      hwBtn.id = "btnDiagSamsungHw";
      hwBtn.className = "ctrl-btn";
      hwBtn.textContent = "Test phần cứng *#0*#";
      hwBtn.title = "Mở trình test RGB điểm chết màn hình, cảm ứng & loa của Samsung";
      hwBtn.addEventListener("click", async () => {
        const r = await callApi("launch_samsung_hw_test", dev.serial);
        if (r.ok) {
          setStatus("Đã mở trình test phần cứng Samsung trên điện thoại.", "success");
        } else {
          setStatus(r.error || "Không mở được trình test phần cứng.", "error");
        }
      });
      touchBtns.appendChild(hwBtn);
      touchBlock.appendChild(touchBtns);
      el.diagBody.appendChild(touchBlock);

      // 3. Connectivity & Recent App Crashes/ANRs
      const connBlock = doc.createElement("div");
      connBlock.className = "diag-block";
      connBlock.innerHTML = `
        <div class="diag-block-title">Kết nối mạng &amp; Ứng dụng lỗi</div>
        <div class="diag-grid-2">
          <div class="diag-stat">
            <span class="diag-stat-label">Wi-Fi • Sóng</span>
            <span class="diag-stat-val">${wifi.ssid || "—"} (${wifi.quality || "—"})</span>
          </div>
          <div class="diag-stat">
            <span class="diag-stat-label">Tốc độ • Ping</span>
            <span class="diag-stat-val">${wifi.link_mbps != null ? wifi.link_mbps + " Mbps" : "—"} • ${diag.ping_ms != null ? diag.ping_ms + " ms" : "Lỗi mạng"}</span>
          </div>
        </div>
      `;

      const crashes = diag.crashes || [];
      if (crashes.length === 0) {
        const okMsg = doc.createElement("div");
        okMsg.className = "help-text";
        okMsg.textContent = "Không ghi nhận ứng dụng nào bị Crash / Treo (ANR) gần đây.";
        connBlock.appendChild(okMsg);
      } else {
        for (const c of crashes.slice(0, 6)) {
          const item = doc.createElement("div");
          item.className = "crash-item";
          const info = doc.createElement("div");
          info.className = "crash-info";
          info.innerHTML = `<div class="crash-pkg"></div><div class="crash-meta"></div>`;
          info.querySelector(".crash-pkg").textContent = c.package || c.type;
          info.querySelector(".crash-meta").textContent = `${c.type} • ${c.timestamp}`;
          item.appendChild(info);

          if (c.package) {
            const stopBtn = doc.createElement("button");
            stopBtn.type = "button";
            stopBtn.className = "btn-outline xs";
            stopBtn.textContent = "Buộc dừng";
            stopBtn.addEventListener("click", async () => {
              const r = await callApi("force_stop_package", dev.serial, c.package);
              if (r.ok) setStatus(`Đã buộc dừng ${c.package}.`, "success");
              else setStatus(r.error || "Không buộc dừng được.", "error");
            });
            item.appendChild(stopBtn);
          }
          connBlock.appendChild(item);
        }
      }
      el.diagBody.appendChild(connBlock);
    }

    // Core API Actions
    async function refreshDevices(triggerAutoMirror = true) {
      if (state.scanning) return;
      state.scanning = true;
      try {
        const res = await callApi("scan_devices", triggerAutoMirror);
        if (!res.ok) {
          setStatus(res.error || "Không quét được thiết bị.", "error");
          return;
        }
        state.devices = res.data.devices || [];
        renderDevices();
        if (res.data.auto_mirrored && res.data.auto_mirrored.length > 0) {
          setStatus("Đã tự động mở màn hình cho thiết bị đã lưu.", "success");
        }
      } finally {
        state.scanning = false;
      }
    }

    async function saveSettingPatch(patch) {
      state.settings = Object.assign({}, state.settings, patch);
      renderSettings();
      if ("zoom_mode" in patch) {
        renderWorkspaceStage();
      } else if ("sidebar_collapsed" in patch) {
        renderWorkspaceStage();
        setTimeout(() => scheduleStageRender(), 210);
      }
      const res = await callApi("update_settings", patch);
      if (res.ok && res.data) {
        state.settings = res.data;
        renderSettings();
      } else if (!res.ok) {
        setStatus(res.error || "Không lưu được cài đặt.", "error");
      }
    }

    async function handleToggleAlwaysOnTop() {
      const next = !Boolean(state.settings.always_on_top);
      state.settings.always_on_top = next;
      renderAlwaysOnTopState();
      const res = await callApi("set_always_on_top", next);
      if (!res.ok) {
        state.settings.always_on_top = !next;
        renderAlwaysOnTopState();
        setStatus(res.error || "Không bật/tắt được chế độ Luôn nổi.", "error");
      } else {
        setStatus(next ? "Đã ghim cửa sổ luôn nổi trên cùng." : "Đã tắt chế độ luôn nổi.", "success");
      }
    }

    async function startMirrorForDevice(dev) {
      if (!dev || !dev.online) return;
      if (state.demoCount > 0) {
        state.demoCount = 0;
        el.selectDemoCount.value = "0";
      }
      setStatus(`Đang mở màn hình ${dev.display_name}...`, "neutral");
      dev.mirroring = true;
      renderWorkspaceStage();

      const vp = el.stageGrid.querySelector(`.phone-slot-viewport[data-viewport-serial="${CSS.escape(dev.serial)}"]`);
      let initialSlot = null;
      if (vp) {
        const dpr = root.devicePixelRatio || 1;
        const r = vp.getBoundingClientRect();
        initialSlot = {
          x: Math.round(r.left * dpr),
          y: Math.round(r.top * dpr),
          width: Math.round(r.width * dpr),
          height: Math.round(r.height * dpr),
        };
      }

      const res = await callApi("start_mirror", dev.serial, dev.display_name, initialSlot);
      if (!res.ok) {
        dev.mirroring = false;
        setStatus(res.error || "Không mở được scrcpy.", "error");
      } else {
        setStatus(`Đang chiếu ${dev.display_name} (60fps).`, "success");
        setTimeout(() => syncNativeOverlaySlots(), 550);
        setTimeout(() => syncNativeOverlaySlots(), 1200);
      }
      await refreshDevices(false);
    }

    async function stopMirrorForDevice(dev) {
      if (!dev) return;
      const res = await callApi("stop_mirror", dev.serial);
      if (!res.ok) {
        setStatus(res.error || "Không dừng được màn hình.", "error");
      } else {
        setStatus(`Đã đóng màn hình ${dev.display_name}.`, "neutral");
      }
      await refreshDevices(false);
    }

    async function toggleMirrorForDevice(dev) {
      if (!dev || !dev.online) return;
      if (dev.mirroring) await stopMirrorForDevice(dev);
      else await startMirrorForDevice(dev);
    }

    async function handleMirrorAllOnline() {
      const targets = state.devices.filter((d) => d.online && !d.mirroring);
      if (targets.length === 0) {
        setStatus("Tất cả thiết bị đang kết nối đều đã mở màn hình.", "neutral");
        return;
      }
      for (const dev of targets) {
        await startMirrorForDevice(dev);
      }
    }

    async function toggleDisplayPowerFor(dev) {
      if (!dev || !dev.online) return;
      const wantOn = Boolean(dev.screen_off);
      setStatus(wantOn ? `Đang bật sáng lại màn hình ${dev.display_name}...` : `Đang tắt màn hình vật lý ${dev.display_name} (giữ ĐK)...`, "neutral");
      const res = await callApi("set_display_power", dev.serial, wantOn);
      if (!res.ok) {
        setStatus(res.error || "Không điều chỉnh được màn hình vật lý.", "error");
        return;
      }
      dev.screen_off = !wantOn;
      renderControlStates();
      renderWorkspaceStage();
      setStatus(
        wantOn
          ? `Đã bật sáng lại màn hình ${dev.display_name}.`
          : `Đã tắt màn hình vật lý ${dev.display_name} — vẫn điều khiển trên PC bình thường.`,
        "success"
      );
    }

    async function handleToggleTouchDot() {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      const nextVal = !Boolean(dev.show_touches);
      const res = await callApi("set_show_touches", dev.serial, nextVal);
      if (!res.ok) {
        setStatus(res.error || "Không bật/tắt được chấm chạm trắng.", "error");
        return;
      }
      dev.show_touches = nextVal;
      renderControlStates();
      setStatus(nextVal ? "Đã bật chấm tròn trắng khi chạm màn hình." : "Đã tắt chấm chạm trắng.", "success");
    }

    async function handleSwipe(direction) {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      const res = await callApi("swipe", dev.serial, direction, state.settings.swipe_step);
      if (!res.ok) setStatus(res.error || "Không gửi được thao tác vuốt.", "error");
    }

    async function handleAction(action) {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      const res = await callApi("send_action", dev.serial, action);
      if (!res.ok) {
        setStatus(res.error || "Không gửi được lệnh điều khiển.", "error");
        return;
      }
      if (action === "rotate" && res.data) {
        dev.orientation = res.data.orientation;
        if (res.data.screen_width && res.data.screen_height) {
          dev.screen_width = res.data.screen_width;
          dev.screen_height = res.data.screen_height;
        }
        renderControlStates();
        renderWorkspaceStage();
        setTimeout(() => syncNativeOverlaySlots(), 250);
        setStatus(
          dev.orientation === 1 || dev.orientation === 3 ? "Đã xoay ngang khung theo điện thoại." : "Đã xoay dọc khung theo điện thoại.",
          "success"
        );
      }
    }

    async function handleQuickApp(appKey) {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      const res = await callApi("launch_quick_app", dev.serial, appKey);
      if (!res.ok) setStatus(res.error || "Không mở được ứng dụng nhanh.", "error");
    }

    async function handleScreenshotFor(dev) {
      if (!dev || !dev.online) return;
      setStatus(`Đang chụp ảnh màn hình ${dev.display_name}...`, "neutral");
      const res = await callApi("take_screenshot", dev.serial, dev.display_name);
      if (!res.ok) {
        setStatus(res.error || "Chụp ảnh thất bại.", "error");
        return;
      }
      state.lastScreenshotPath = res.data.path;
      const clipNote = res.data.copied_to_clipboard ? " (đã chép Clipboard)" : "";
      setStatus(
        `Đã lưu ${res.data.filename}${clipNote}`,
        "success",
        "Mở ảnh",
        () => callApi("open_file", state.lastScreenshotPath)
      );
    }

    async function handleSwitchWifi() {
      const dev = getSelectedDevice();
      if (!dev || !dev.online || dev.transport !== "usb") return;
      setStatus("Đang bật chế độ Wi-Fi ADB cho điện thoại...", "neutral");
      const res = await callApi("enable_wifi_for_device", dev.serial, dev.id);
      if (!res.ok) {
        setStatus(res.error || "Không chuyển sang Wi-Fi được.", "error");
        return;
      }
      setStatus(`Đã kết nối Wi-Fi ${res.data.target}. Bạn có thể rút cáp USB!`, "success");
      await refreshDevices(false);
    }

    async function handleReconnectSavedWifi(dev) {
      if (!dev.wifi_ip) return;
      setStatus(`Đang kết nối Wi-Fi tới ${dev.wifi_ip}:5555...`, "neutral");
      const res = await callApi("connect_wifi", `${dev.wifi_ip}:5555`);
      if (!res.ok) {
        setStatus(res.error || "Không kết nối được Wi-Fi.", "error");
        return;
      }
      setStatus(`Đã kết nối lại ${dev.display_name} qua Wi-Fi.`, "success");
      await refreshDevices(false);
    }

    async function handleSendFile() {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      const res = await callApi("pick_and_send_file", dev.serial);
      if (!res.ok) {
        setStatus(res.error || "Gửi tệp thất bại.", "error");
        return;
      }
      if (res.data && res.data.cancelled) return;
      setStatus(res.data.message || "Đã gửi tệp thành công.", "success");
    }

    async function handleDeleteSaved(dev) {
      const res = await callApi("delete_saved_device", dev.id);
      if (!res.ok) {
        setStatus(res.error || "Không xóa được thiết bị.", "error");
        return;
      }
      setStatus(`Đã xóa ${dev.display_name} khỏi danh sách đã lưu.`, "neutral");
      await refreshDevices(false);
    }

    async function handleSaveRename() {
      if (!state.renamingDeviceId) return;
      const nickname = el.inputDeviceNickname.value.trim();
      const res = await callApi("rename_device", state.renamingDeviceId, nickname);
      if (!res.ok) {
        setStatus(res.error || "Không đổi tên được.", "error");
        return;
      }
      closeDrawers();
      setStatus("Đã cập nhật tên thiết bị.", "success");
      await refreshDevices(false);
    }

    async function handleWifiConnectSubmit() {
      const addr = el.inputWifiAddr.value.trim();
      if (!addr) {
        setStatus("Hãy nhập địa chỉ IP của điện thoại.", "error");
        return;
      }
      setStatus(`Đang kết nối tới ${addr}...`, "neutral");
      const res = await callApi("connect_wifi", addr);
      if (!res.ok) {
        setStatus(res.error || "Kết nối Wi-Fi thất bại.", "error");
        return;
      }
      closeDrawers();
      setStatus(`Đã kết nối Wi-Fi tới ${res.data.target}.`, "success");
      await refreshDevices(false);
    }

    async function handleWifiPairSubmit() {
      const pairAddr = el.inputPairAddr.value.trim();
      const pairCode = el.inputPairCode.value.trim();
      const connectAddr = el.inputConnectAfterPair.value.trim();
      setStatus("Đang ghép nối không dây...", "neutral");
      const res = await callApi("pair_and_connect_wifi", pairAddr, pairCode, connectAddr);
      if (!res.ok) {
        setStatus(res.error || "Ghép nối Wi-Fi thất bại.", "error");
        return;
      }
      closeDrawers();
      setStatus("Đã ghép nối Wi-Fi thành công.", "success");
      await refreshDevices(false);
    }

    function switchAddTab(tabName) {
      for (const btn of tabButtons) {
        const active = btn.dataset.tab === tabName;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
      }
      for (const name of ["connect", "pair", "guide"]) {
        const panel = doc.getElementById(`tab-${name}`);
        if (panel) panel.classList.toggle("hidden", name !== tabName);
      }
    }

    function bindEvents() {
      el.btnToggleSidebar.addEventListener("click", () => {
        saveSettingPatch({ sidebar_collapsed: !state.settings.sidebar_collapsed });
      });

      el.btnPhoneOnly.addEventListener("click", () => {
        state.phoneOnlyMode = true;
        applyPhoneOnlyState();
      });
      el.btnExitPhoneOnly.addEventListener("click", () => {
        state.phoneOnlyMode = false;
        applyPhoneOnlyState();
      });

      el.btnAlwaysOnTop.addEventListener("click", handleToggleAlwaysOnTop);
      el.btnSideAlwaysOnTop.addEventListener("click", handleToggleAlwaysOnTop);
      el.btnMiniAlwaysOnTop.addEventListener("click", handleToggleAlwaysOnTop);

      el.btnToggleFullscreen.addEventListener("click", () => {
        callApi("toggle_fullscreen");
        setTimeout(() => scheduleStageRender(), 180);
      });

      for (const btn of zoomButtons) {
        btn.addEventListener("click", () => saveSettingPatch({ zoom_mode: btn.dataset.zoom }));
      }

      el.selectDemoCount.addEventListener("change", () => {
        state.demoCount = Number(el.selectDemoCount.value) || 0;
        renderWorkspaceStage();
      });

      el.btnEmptyDemo4.addEventListener("click", () => {
        state.demoCount = 4;
        el.selectDemoCount.value = "4";
        renderWorkspaceStage();
      });

      el.btnEmptyStartMirror.addEventListener("click", () => toggleMirrorForDevice(getSelectedDevice()));
      el.btnToggleMirror.addEventListener("click", () => toggleMirrorForDevice(getSelectedDevice()));
      el.btnMirrorAll.addEventListener("click", handleMirrorAllOnline);
      el.btnRefresh.addEventListener("click", () => refreshDevices(false));

      el.btnScreenshot.addEventListener("click", () => handleScreenshotFor(getSelectedDevice()));
      el.btnMiniScreenshot.addEventListener("click", () => handleScreenshotFor(getSelectedDevice()));
      el.btnMiniRotate.addEventListener("click", () => handleAction("rotate"));

      el.btnToggleScreenOff.addEventListener("click", () => toggleDisplayPowerFor(getSelectedDevice()));
      el.btnTopScreenOff.addEventListener("click", () => toggleDisplayPowerFor(getSelectedDevice()));
      el.btnMiniScreenOff.addEventListener("click", () => toggleDisplayPowerFor(getSelectedDevice()));
      el.btnToggleTouchDot.addEventListener("click", handleToggleTouchDot);

      el.btnSwitchWifi.addEventListener("click", handleSwitchWifi);
      el.btnSendFile.addEventListener("click", handleSendFile);
      el.btnOpenScreenshots.addEventListener("click", () => callApi("open_screenshot_folder"));

      el.btnStatusAction.addEventListener("click", () => {
        if (typeof statusActionHandler === "function") statusActionHandler();
      });

      el.chkAutoMirrorAll.addEventListener("change", () => saveSettingPatch({ auto_mirror_saved: el.chkAutoMirrorAll.checked }));
      el.chkTurnScreenOff.addEventListener("change", () => saveSettingPatch({ turn_screen_off: el.chkTurnScreenOff.checked }));
      el.chkStayAwake.addEventListener("change", () => saveSettingPatch({ stay_awake: el.chkStayAwake.checked }));
      el.chkEnableAudio.addEventListener("change", () => saveSettingPatch({ enable_audio: el.chkEnableAudio.checked }));

      for (const btn of qualityButtons) {
        btn.addEventListener("click", () => saveSettingPatch({ quality: btn.dataset.quality }));
      }
      for (const btn of stepButtons) {
        btn.addEventListener("click", () => saveSettingPatch({ swipe_step: btn.dataset.step }));
      }
      for (const btn of swipeButtons) {
        btn.addEventListener("click", () => handleSwipe(btn.dataset.swipe));
      }
      for (const btn of actionButtons) {
        btn.addEventListener("click", () => handleAction(btn.dataset.action));
      }
      for (const btn of quickAppButtons) {
        btn.addEventListener("click", () => handleQuickApp(btn.dataset.app));
      }

      // Drawers
      el.btnOpenAddDrawer.addEventListener("click", () => {
        openDrawer("add");
        el.inputWifiAddr.focus();
      });
      el.btnOpenAppsDrawer.addEventListener("click", () => openAppsDrawer(false));
      el.btnReloadApps.addEventListener("click", () => openAppsDrawer(true));
      el.inputSearchApps.addEventListener("input", () => renderAppsGrid(el.inputSearchApps.value));
      for (const btn of appFilterButtons) {
        btn.addEventListener("click", () => {
          state.appFilter = btn.dataset.appFilter;
          for (const b of appFilterButtons) b.classList.toggle("active", b === btn);
          renderAppsGrid(el.inputSearchApps.value);
        });
      }

      el.btnOpenDiagDrawer.addEventListener("click", openDiagnosticsDrawer);
      el.btnSideDiagDrawer.addEventListener("click", openDiagnosticsDrawer);
      el.btnReloadDiag.addEventListener("click", openDiagnosticsDrawer);

      for (const btn of closeDrawerButtons) {
        btn.addEventListener("click", closeDrawers);
      }
      for (const btn of tabButtons) {
        btn.addEventListener("click", () => switchAddTab(btn.dataset.tab));
      }
      el.btnDoWifiConnect.addEventListener("click", handleWifiConnectSubmit);
      el.btnDoWifiPair.addEventListener("click", handleWifiPairSubmit);
      el.btnSaveRename.addEventListener("click", handleSaveRename);
      el.inputDeviceNickname.addEventListener("keydown", (evt) => {
        if (evt.key === "Enter") handleSaveRename();
        if (evt.key === "Escape") closeDrawers();
      });

      // Keyboard shortcuts
      doc.addEventListener("keydown", (evt) => {
        if ((evt.ctrlKey || evt.metaKey) && evt.shiftKey && evt.key.toLowerCase() === "h") {
          evt.preventDefault();
          state.phoneOnlyMode = !state.phoneOnlyMode;
          applyPhoneOnlyState();
        } else if ((evt.ctrlKey || evt.metaKey) && evt.key.toLowerCase() === "b") {
          evt.preventDefault();
          saveSettingPatch({ sidebar_collapsed: !state.settings.sidebar_collapsed });
        } else if (evt.key === "F11") {
          evt.preventDefault();
          callApi("toggle_fullscreen");
        } else if (evt.key === "Escape") {
          if (state.activeDrawer) closeDrawers();
          else if (state.phoneOnlyMode) {
            state.phoneOnlyMode = false;
            applyPhoneOnlyState();
          }
        }
      });

      el.workspaceStage.addEventListener("scroll", () => syncNativeOverlaySlots(), { passive: true });
      root.addEventListener("resize", () => scheduleStageRender());
      if (typeof ResizeObserver !== "undefined") {
        state.resizeObserver = new ResizeObserver(() => scheduleStageRender());
        state.resizeObserver.observe(el.workspaceStage);
      }
    }

    async function init(startPolling = true) {
      bindEvents();
      const res = await callApi("get_initial_state");
      if (res.ok && res.data) {
        state.tools = res.data.tools;
        state.settings = Object.assign({}, state.settings, res.data.settings || {});
        state.devices = Array.isArray(res.data.devices) ? res.data.devices : [];
        renderSettings();
        renderDevices();
      } else {
        setStatus(res.error || "Không khởi tạo được ứng dụng.", "error");
      }

      if (startPolling) {
        state.pollTimer = setInterval(() => refreshDevices(true), POLL_INTERVAL_MS);
      }
    }

    function destroy() {
      if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
      }
      if (state.resizeObserver) {
        state.resizeObserver.disconnect();
        state.resizeObserver = null;
      }
    }

    return { init, destroy, state, refreshDevices, renderWorkspaceStage };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { createController };
  } else {
    root.PhoneControlUI = { createController };
    const boot = () => {
      const ctrl = createController(document, () => window.pywebview && window.pywebview.api, root.PhoneControlLayout);
      root.__phoneControl = ctrl;
      ctrl.init(true);
    };
    if (window.pywebview && window.pywebview.api) {
      boot();
    } else {
      window.addEventListener("pywebviewready", boot, { once: true });
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
