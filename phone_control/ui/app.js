(function (root) {
  "use strict";

  const POLL_INTERVAL_MS = 2500;
  const ZOOM_LABELS = {
    fit: "Tự khớp",
    fill: "Lấp đầy",
    "50": "50%",
    "75": "75%",
    "100": "100%",
    "125": "125%",
    "150": "150%",
  };

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
      demoCount: 0,
      activeDrawer: null, // null | "add" | "apps" | "rename"
      renamingDeviceId: null,
      installedApps: [],
      appsSerialLoaded: null,
      lastScreenshotPath: "",
      pollTimer: null,
      resizeObserver: null,
      syncRaf: null,
      scanning: false,
    };

    const el = {
      btnToggleSidebar: doc.getElementById("btnToggleSidebar"),
      controlSidebar: doc.getElementById("controlSidebar"),
      sidebarMainView: doc.getElementById("sidebarMainView"),
      toolStatusText: doc.getElementById("toolStatusText"),
      zoomBar: doc.getElementById("zoomBar"),
      selectDemoCount: doc.getElementById("selectDemoCount"),
      btnTopScreenOff: doc.getElementById("btnTopScreenOff"),
      btnTopScreenshot: doc.getElementById("btnTopScreenshot"),
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
      btnScreenOffLive: doc.getElementById("btnScreenOffLive"),
      btnScreenOnLive: doc.getElementById("btnScreenOnLive"),
      btnToggleTouchDot: doc.getElementById("btnToggleTouchDot"),
      chkTurnScreenOff: doc.getElementById("chkTurnScreenOff"),
      chkStayAwake: doc.getElementById("chkStayAwake"),
      chkEnableAudio: doc.getElementById("chkEnableAudio"),

      btnOpenAppsDrawer: doc.getElementById("btnOpenAppsDrawer"),
      btnSendFile: doc.getElementById("btnSendFile"),
      btnOpenScreenshots: doc.getElementById("btnOpenScreenshots"),

      drawerAddDevice: doc.getElementById("drawerAddDevice"),
      drawerApps: doc.getElementById("drawerApps"),
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
      } else if (dev.online) {
        el.selectedDeviceBadge.textContent = dev.display_name;
        el.selectedDeviceBadge.className = "device-pill online";
      } else {
        el.selectedDeviceBadge.textContent = `${dev.display_name} (chưa cắm)`;
        el.selectedDeviceBadge.className = "device-pill";
      }

      el.btnToggleMirror.disabled = !canControl;
      el.btnEmptyStartMirror.disabled = !canControl;
      el.btnScreenshot.disabled = !canControl;
      el.btnTopScreenshot.disabled = !canControl;
      el.btnScreenOffLive.disabled = !canControl;
      el.btnTopScreenOff.disabled = !canControl;
      el.btnScreenOnLive.disabled = !canControl;
      el.btnToggleTouchDot.disabled = !canControl;
      el.btnOpenAppsDrawer.disabled = !canControl;
      el.btnSendFile.disabled = !canControl;
      el.btnSwitchWifi.disabled = !(canControl && dev.transport === "usb");

      const touchOn = Boolean(dev && dev.show_touches);
      el.btnToggleTouchDot.classList.toggle("active", touchOn);
      el.btnToggleTouchDot.setAttribute("aria-pressed", touchOn ? "true" : "false");

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
          offBtn.className = "icon-btn mini";
          offBtn.title = "Tắt màn hình vật lý máy này";
          offBtn.setAttribute("aria-label", `Tắt màn hình ${item.display_name}`);
          offBtn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';
          offBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            handleDisplayPowerFor(item, false);
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

    // Drawer navigation (lives inside left sidebar so scrcpy overlay never occludes forms)
    function openDrawer(name) {
      if (state.settings.sidebar_collapsed) {
        state.settings.sidebar_collapsed = false;
        applySidebarState();
      }
      state.activeDrawer = name;
      el.drawerAddDevice.classList.toggle("hidden", name !== "add");
      el.drawerApps.classList.toggle("hidden", name !== "apps");
      el.drawerRename.classList.toggle("hidden", name !== "rename");
    }

    function closeDrawers() {
      state.activeDrawer = null;
      state.renamingDeviceId = null;
      el.drawerAddDevice.classList.add("hidden");
      el.drawerApps.classList.add("hidden");
      el.drawerRename.classList.add("hidden");
    }

    function openRenameDrawer(dev) {
      state.renamingDeviceId = dev.id;
      el.inputDeviceNickname.value = dev.nickname || dev.display_name || "";
      openDrawer("rename");
      el.inputDeviceNickname.focus();
      el.inputDeviceNickname.select();
    }

    async function openAppsDrawer(forceRefresh = false) {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      openDrawer("apps");
      el.inputSearchApps.value = "";
      if (!forceRefresh && state.appsSerialLoaded === dev.serial && state.installedApps.length > 0) {
        renderAppsList("");
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
      renderAppsList("");
      el.inputSearchApps.focus();
    }

    function renderAppsList(query) {
      const q = (query || "").trim().toLowerCase();
      const filtered = q
        ? state.installedApps.filter(
            (a) => a.name.toLowerCase().includes(q) || a.package.toLowerCase().includes(q)
          )
        : state.installedApps;
      el.appPickerList.innerHTML = "";
      if (filtered.length === 0) {
        el.appPickerList.innerHTML = '<div class="empty-inline">Không tìm thấy ứng dụng phù hợp.</div>';
        return;
      }
      const dev = getSelectedDevice();
      for (const app of filtered) {
        const btn = doc.createElement("button");
        btn.type = "button";
        btn.className = "app-row";
        btn.innerHTML = `<div><div class="app-row-name"></div><div class="app-row-pkg"></div></div>`;
        btn.querySelector(".app-row-name").textContent = app.name;
        btn.querySelector(".app-row-pkg").textContent = app.package;
        btn.addEventListener("click", async () => {
          if (!dev || !dev.online) return;
          setStatus(`Đang mở ${app.name}...`, "neutral");
          const res = await callApi("launch_package", dev.serial, app.package);
          if (!res.ok) {
            setStatus(res.error || `Không mở được ${app.name}.`, "error");
          } else {
            setStatus(`Đã mở ${app.name}.`, "success");
          }
        });
        el.appPickerList.appendChild(btn);
      }
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

    async function startMirrorForDevice(dev) {
      if (!dev || !dev.online) return;
      if (state.demoCount > 0) {
        state.demoCount = 0;
        el.selectDemoCount.value = "0";
      }
      setStatus(`Đang mở màn hình ${dev.display_name}...`, "neutral");
      // Optimistically show slot so we can compute exact target rect for scrcpy
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
      if (dev.mirroring) {
        await stopMirrorForDevice(dev);
      } else {
        await startMirrorForDevice(dev);
      }
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

    async function handleDisplayPowerFor(dev, on) {
      if (!dev || !dev.online) return;
      setStatus(on ? `Đang bật sáng màn hình ${dev.display_name}...` : `Đang tắt màn hình vật lý ${dev.display_name} (giữ điều khiển)...`, "neutral");
      const res = await callApi("set_display_power", dev.serial, on);
      if (!res.ok) {
        setStatus(res.error || "Không điều chỉnh được màn hình vật lý.", "error");
      } else {
        setStatus(on ? `Đã bật sáng màn hình ${dev.display_name}.` : `Đã tắt màn hình vật lý ${dev.display_name} — vẫn điều khiển bình thường.`, "success");
      }
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
      if (!res.ok) {
        setStatus(res.error || "Không gửi được thao tác vuốt.", "error");
      }
    }

    async function handleAction(action) {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      const res = await callApi("send_action", dev.serial, action);
      if (!res.ok) {
        setStatus(res.error || "Không gửi được lệnh điều khiển.", "error");
      }
    }

    async function handleQuickApp(appKey) {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      const res = await callApi("launch_quick_app", dev.serial, appKey);
      if (!res.ok) {
        setStatus(res.error || "Không mở được ứng dụng nhanh.", "error");
      }
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
      el.btnTopScreenshot.addEventListener("click", () => handleScreenshotFor(getSelectedDevice()));

      el.btnScreenOffLive.addEventListener("click", () => handleDisplayPowerFor(getSelectedDevice(), false));
      el.btnTopScreenOff.addEventListener("click", () => handleDisplayPowerFor(getSelectedDevice(), false));
      el.btnScreenOnLive.addEventListener("click", () => handleDisplayPowerFor(getSelectedDevice(), true));
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
      el.inputSearchApps.addEventListener("input", () => renderAppsList(el.inputSearchApps.value));

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

      // Keyboard shortcuts (Ctrl+B toggle sidebar, F11 fullscreen)
      doc.addEventListener("keydown", (evt) => {
        if ((evt.ctrlKey || evt.metaKey) && evt.key.toLowerCase() === "b") {
          evt.preventDefault();
          saveSettingPatch({ sidebar_collapsed: !state.settings.sidebar_collapsed });
        } else if (evt.key === "F11") {
          evt.preventDefault();
          callApi("toggle_fullscreen");
        } else if (evt.key === "Escape" && state.activeDrawer) {
          closeDrawers();
        }
      });

      // Keep docked scrcpy windows locked to viewport slots during scroll/resize
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
