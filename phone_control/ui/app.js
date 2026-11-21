(function (root) {
  "use strict";

  const POLL_INTERVAL_MS = 2500;

  function createController(doc, getApi) {
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
      },
      tools: null,
      renamingDeviceId: null,
      lastScreenshotPath: "",
      pollTimer: null,
      scanning: false,
    };

    const el = {
      toolStatusText: doc.getElementById("toolStatusText"),
      btnRefresh: doc.getElementById("btnRefresh"),
      btnOpenWifiModal: doc.getElementById("btnOpenWifiModal"),
      chkAutoMirrorAll: doc.getElementById("chkAutoMirrorAll"),
      deviceList: doc.getElementById("deviceList"),
      selectedDeviceBadge: doc.getElementById("selectedDeviceBadge"),
      btnToggleMirror: doc.getElementById("btnToggleMirror"),
      mirrorBtnLabel: doc.getElementById("mirrorBtnLabel"),
      btnScreenshot: doc.getElementById("btnScreenshot"),
      btnSwitchWifi: doc.getElementById("btnSwitchWifi"),
      btnSendFile: doc.getElementById("btnSendFile"),
      btnOpenScreenshots: doc.getElementById("btnOpenScreenshots"),
      chkTurnScreenOff: doc.getElementById("chkTurnScreenOff"),
      chkStayAwake: doc.getElementById("chkStayAwake"),
      chkAlwaysOnTop: doc.getElementById("chkAlwaysOnTop"),
      chkEnableAudio: doc.getElementById("chkEnableAudio"),
      statusBar: doc.getElementById("statusBar"),
      statusMessage: doc.getElementById("statusMessage"),
      btnStatusAction: doc.getElementById("btnStatusAction"),
      wifiModal: doc.getElementById("wifiModal"),
      btnCloseWifiModal: doc.getElementById("btnCloseWifiModal"),
      inputWifiAddr: doc.getElementById("inputWifiAddr"),
      btnDoWifiConnect: doc.getElementById("btnDoWifiConnect"),
      inputPairAddr: doc.getElementById("inputPairAddr"),
      inputPairCode: doc.getElementById("inputPairCode"),
      inputConnectAfterPair: doc.getElementById("inputConnectAfterPair"),
      btnDoWifiPair: doc.getElementById("btnDoWifiPair"),
      renameModal: doc.getElementById("renameModal"),
      btnCloseRenameModal: doc.getElementById("btnCloseRenameModal"),
      btnCancelRename: doc.getElementById("btnCancelRename"),
      btnSaveRename: doc.getElementById("btnSaveRename"),
      inputDeviceNickname: doc.getElementById("inputDeviceNickname"),
    };

    const qualityButtons = Array.from(doc.querySelectorAll(".seg-btn[data-quality]"));
    const padActionButtons = Array.from(doc.querySelectorAll(".pad-btn[data-action]"));
    const modalTabButtons = Array.from(doc.querySelectorAll(".tab-btn[data-tab]"));

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
      const current = getSelectedDevice();
      if (current) return;
      const firstOnline = state.devices.find((d) => d.online);
      const fallback = firstOnline || state.devices[0] || null;
      state.selectedId = fallback ? fallback.id : null;
    }

    function renderToolStatus() {
      if (!state.tools) return;
      if (state.tools.adb_available && state.tools.scrcpy_available) {
        const onlineCount = state.devices.filter((d) => d.online).length;
        el.toolStatusText.textContent = onlineCount > 0
          ? `scrcpy sẵn sàng • ${onlineCount} thiết bị đang kết nối`
          : "scrcpy sẵn sàng • Chờ kết nối thiết bị";
      } else {
        el.toolStatusText.textContent = "Thiếu adb hoặc scrcpy trên hệ thống";
      }
    }

    function renderSettings() {
      const s = state.settings;
      el.chkAutoMirrorAll.checked = Boolean(s.auto_mirror_saved);
      el.chkTurnScreenOff.checked = Boolean(s.turn_screen_off);
      el.chkStayAwake.checked = Boolean(s.stay_awake);
      el.chkAlwaysOnTop.checked = Boolean(s.always_on_top);
      el.chkEnableAudio.checked = Boolean(s.enable_audio);
      for (const btn of qualityButtons) {
        btn.classList.toggle("active", btn.dataset.quality === s.quality);
      }
    }

    function buildDeviceMeta(dev) {
      if (dev.state === "unauthorized") {
        return "Chờ bấm 'Cho phép' gỡ lỗi USB trên điện thoại";
      }
      if (dev.state === "authorizing") {
        return "Đang xác thực kết nối ADB...";
      }
      if (!dev.online) {
        return dev.wifi_ip
          ? `Chưa kết nối • IP lưu: ${dev.wifi_ip}`
          : "Đã lưu • Cắm cáp USB để kết nối lại";
      }
      const bits = [];
      if (dev.android_version) bits.push(`Android ${dev.android_version}`);
      if (typeof dev.battery === "number") bits.push(`Pin ${dev.battery}%`);
      if (dev.wifi_ip) bits.push(dev.wifi_ip);
      if (bits.length === 0) bits.push(dev.serial);
      return bits.join(" • ");
    }

    function renderDevices() {
      ensureValidSelection();
      renderToolStatus();
      el.deviceList.innerHTML = "";

      if (state.devices.length === 0) {
        const empty = doc.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Chưa có điện thoại nào. Cắm cáp USB (đã bật Gỡ lỗi USB) hoặc bấm '+ Thêm máy'.";
        el.deviceList.appendChild(empty);
        renderControlStates();
        return;
      }

      for (const dev of state.devices) {
        const card = doc.createElement("div");
        card.className = "device-card" + (dev.id === state.selectedId ? " selected" : "");
        card.setAttribute("role", "option");
        card.setAttribute("aria-selected", dev.id === state.selectedId ? "true" : "false");
        card.dataset.deviceId = dev.id;

        const main = doc.createElement("div");
        main.className = "device-main";

        const dot = doc.createElement("span");
        dot.className = "status-dot" + (dev.online ? " online" : dev.state === "unauthorized" || dev.state === "authorizing" ? " warn" : "");
        main.appendChild(dot);

        const info = doc.createElement("div");
        info.className = "device-info";

        const nameRow = doc.createElement("div");
        nameRow.className = "device-name-row";

        const nameSpan = doc.createElement("span");
        nameSpan.className = "device-name";
        nameSpan.textContent = dev.display_name || dev.serial;
        nameRow.appendChild(nameSpan);

        if (dev.online) {
          const transportTag = doc.createElement("span");
          transportTag.className = "tag " + (dev.transport === "wifi" ? "wifi" : "usb");
          transportTag.textContent = dev.transport === "wifi" ? "Wi-Fi" : "USB";
          nameRow.appendChild(transportTag);
        }

        if (dev.mirroring) {
          const liveTag = doc.createElement("span");
          liveTag.className = "tag live";
          liveTag.textContent = "Đang chiếu";
          nameRow.appendChild(liveTag);
        }

        const meta = doc.createElement("div");
        meta.className = "device-meta";
        meta.textContent = buildDeviceMeta(dev);

        info.appendChild(nameRow);
        info.appendChild(meta);
        main.appendChild(info);
        card.appendChild(main);

        const actions = doc.createElement("div");
        actions.className = "device-actions";

        if (!dev.online && dev.wifi_ip) {
          const reconnBtn = doc.createElement("button");
          reconnBtn.type = "button";
          reconnBtn.className = "btn-outline btn-sm";
          reconnBtn.textContent = "Wi-Fi";
          reconnBtn.title = `Kết nối lại Wi-Fi ${dev.wifi_ip}:5555`;
          reconnBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            handleReconnectSavedWifi(dev);
          });
          actions.appendChild(reconnBtn);
        }

        if (dev.saved) {
          const editBtn = doc.createElement("button");
          editBtn.type = "button";
          editBtn.className = "icon-btn mini";
          editBtn.title = "Đặt tên gợi nhớ";
          editBtn.setAttribute("aria-label", `Đổi tên ${dev.display_name}`);
          editBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>';
          editBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            openRenameModal(dev);
          });
          actions.appendChild(editBtn);

          if (!dev.online) {
            const delBtn = doc.createElement("button");
            delBtn.type = "button";
            delBtn.className = "icon-btn mini danger";
            delBtn.title = "Xóa khỏi danh sách đã lưu";
            delBtn.setAttribute("aria-label", `Xóa ${dev.display_name}`);
            delBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path></svg>';
            delBtn.addEventListener("click", (evt) => {
              evt.stopPropagation();
              handleDeleteSaved(dev);
            });
            actions.appendChild(delBtn);
          }
        }

        card.appendChild(actions);
        card.addEventListener("click", () => {
          state.selectedId = dev.id;
          renderDevices();
        });

        el.deviceList.appendChild(card);
      }

      renderControlStates();
    }

    function renderControlStates() {
      const dev = getSelectedDevice();
      const canControl = Boolean(dev && dev.online);

      if (!dev) {
        el.selectedDeviceBadge.textContent = "Chưa chọn máy";
        el.selectedDeviceBadge.className = "selected-badge";
      } else if (dev.online) {
        el.selectedDeviceBadge.textContent = dev.display_name;
        el.selectedDeviceBadge.className = "selected-badge online";
      } else {
        el.selectedDeviceBadge.textContent = `${dev.display_name} (chưa kết nối)`;
        el.selectedDeviceBadge.className = "selected-badge";
      }

      el.btnToggleMirror.disabled = !canControl;
      el.btnScreenshot.disabled = !canControl;
      el.btnSendFile.disabled = !canControl;
      el.btnSwitchWifi.disabled = !(canControl && dev.transport === "usb");

      if (dev && dev.mirroring) {
        el.btnToggleMirror.classList.add("stop-mode");
        el.mirrorBtnLabel.textContent = "Đang chiếu • Dừng";
      } else {
        el.btnToggleMirror.classList.remove("stop-mode");
        el.mirrorBtnLabel.textContent = "Mở màn hình điều khiển";
      }

      for (const btn of padActionButtons) {
        btn.disabled = !canControl;
      }
    }

    async function callApi(method, ...args) {
      const api = getApi();
      if (!api || typeof api[method] !== "function") {
        return { ok: false, error: "Chưa kết nối tới backend Python." };
      }
      return api[method](...args);
    }

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
          setStatus(`Đã tự mở màn hình cho thiết bị đã lưu.`, "success");
        }
      } finally {
        state.scanning = false;
      }
    }

    async function saveSettingPatch(patch) {
      const res = await callApi("update_settings", patch);
      if (res.ok && res.data) {
        state.settings = res.data;
        renderSettings();
      } else if (!res.ok) {
        setStatus(res.error || "Không lưu được cài đặt.", "error");
      }
    }

    async function handleToggleMirror() {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      el.btnToggleMirror.disabled = true;
      try {
        if (dev.mirroring) {
          const res = await callApi("stop_mirror", dev.serial);
          if (!res.ok) {
            setStatus(res.error || "Không dừng được màn hình.", "error");
          } else {
            setStatus(`Đã đóng màn hình ${dev.display_name}.`, "neutral");
          }
        } else {
          setStatus(`Đang mở màn hình ${dev.display_name}...`, "neutral");
          const res = await callApi("start_mirror", dev.serial, dev.display_name);
          if (!res.ok) {
            setStatus(res.error || "Không mở được scrcpy.", "error");
          } else {
            setStatus(`Đang điều khiển ${dev.display_name} bằng scrcpy.`, "success");
          }
        }
        await refreshDevices(false);
      } finally {
        renderControlStates();
      }
    }

    async function handleScreenshot() {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      el.btnScreenshot.disabled = true;
      setStatus(`Đang chụp ảnh màn hình ${dev.display_name}...`, "neutral");
      try {
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
      } finally {
        renderControlStates();
      }
    }

    async function handlePadAction(action) {
      const dev = getSelectedDevice();
      if (!dev || !dev.online) return;
      const res = await callApi("send_action", dev.serial, action);
      if (!res.ok) {
        setStatus(res.error || "Không gửi được lệnh.", "error");
      }
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

    function openWifiModal() {
      el.wifiModal.classList.remove("hidden");
      el.inputWifiAddr.focus();
    }

    function closeWifiModal() {
      el.wifiModal.classList.add("hidden");
    }

    function switchWifiTab(tabName) {
      for (const btn of modalTabButtons) {
        const active = btn.dataset.tab === tabName;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
      }
      for (const name of ["connect", "pair", "guide"]) {
        const panel = doc.getElementById(`tab-${name}`);
        if (panel) panel.classList.toggle("hidden", name !== tabName);
      }
    }

    function openRenameModal(dev) {
      state.renamingDeviceId = dev.id;
      el.inputDeviceNickname.value = dev.nickname || dev.display_name || "";
      el.renameModal.classList.remove("hidden");
      el.inputDeviceNickname.focus();
      el.inputDeviceNickname.select();
    }

    function closeRenameModal() {
      state.renamingDeviceId = null;
      el.renameModal.classList.add("hidden");
    }

    async function handleSaveRename() {
      if (!state.renamingDeviceId) return;
      const nickname = el.inputDeviceNickname.value.trim();
      const res = await callApi("rename_device", state.renamingDeviceId, nickname);
      if (!res.ok) {
        setStatus(res.error || "Không đổi tên được.", "error");
        return;
      }
      closeRenameModal();
      setStatus("Đã cập nhật tên hiển thị của thiết bị.", "success");
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
      closeWifiModal();
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
      closeWifiModal();
      setStatus("Đã ghép nối Wi-Fi thành công!", "success");
      await refreshDevices(false);
    }

    function bindEvents() {
      el.btnRefresh.addEventListener("click", () => refreshDevices(false));
      el.btnToggleMirror.addEventListener("click", handleToggleMirror);
      el.btnScreenshot.addEventListener("click", handleScreenshot);
      el.btnSwitchWifi.addEventListener("click", handleSwitchWifi);
      el.btnSendFile.addEventListener("click", handleSendFile);
      el.btnOpenScreenshots.addEventListener("click", () => callApi("open_screenshot_folder"));

      el.btnStatusAction.addEventListener("click", () => {
        if (typeof statusActionHandler === "function") statusActionHandler();
      });

      el.chkAutoMirrorAll.addEventListener("change", () =>
        saveSettingPatch({ auto_mirror_saved: el.chkAutoMirrorAll.checked })
      );
      el.chkTurnScreenOff.addEventListener("change", () =>
        saveSettingPatch({ turn_screen_off: el.chkTurnScreenOff.checked })
      );
      el.chkStayAwake.addEventListener("change", () =>
        saveSettingPatch({ stay_awake: el.chkStayAwake.checked })
      );
      el.chkAlwaysOnTop.addEventListener("change", () =>
        saveSettingPatch({ always_on_top: el.chkAlwaysOnTop.checked })
      );
      el.chkEnableAudio.addEventListener("change", () =>
        saveSettingPatch({ enable_audio: el.chkEnableAudio.checked })
      );

      for (const btn of qualityButtons) {
        btn.addEventListener("click", () => saveSettingPatch({ quality: btn.dataset.quality }));
      }

      for (const btn of padActionButtons) {
        btn.addEventListener("click", () => handlePadAction(btn.dataset.action));
      }

      el.btnOpenWifiModal.addEventListener("click", openWifiModal);
      el.btnCloseWifiModal.addEventListener("click", closeWifiModal);
      el.wifiModal.addEventListener("click", (evt) => {
        if (evt.target === el.wifiModal) closeWifiModal();
      });
      for (const btn of modalTabButtons) {
        btn.addEventListener("click", () => switchWifiTab(btn.dataset.tab));
      }
      el.btnDoWifiConnect.addEventListener("click", handleWifiConnectSubmit);
      el.btnDoWifiPair.addEventListener("click", handleWifiPairSubmit);

      el.btnCloseRenameModal.addEventListener("click", closeRenameModal);
      el.btnCancelRename.addEventListener("click", closeRenameModal);
      el.btnSaveRename.addEventListener("click", handleSaveRename);
      el.renameModal.addEventListener("click", (evt) => {
        if (evt.target === el.renameModal) closeRenameModal();
      });
      el.inputDeviceNickname.addEventListener("keydown", (evt) => {
        if (evt.key === "Enter") handleSaveRename();
        if (evt.key === "Escape") closeRenameModal();
      });
    }

    async function init(startPolling = true) {
      bindEvents();
      const res = await callApi("get_initial_state");
      if (res.ok && res.data) {
        state.tools = res.data.tools;
        state.settings = Object.assign({}, state.settings, res.data.settings || {});
        state.devices = (res.data.devices && res.data.devices.devices) || res.data.devices || [];
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
    }

    return { init, destroy, state, refreshDevices };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { createController };
  } else {
    root.PhoneControlUI = { createController };
    const boot = () => {
      const ctrl = createController(document, () => window.pywebview && window.pywebview.api);
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
