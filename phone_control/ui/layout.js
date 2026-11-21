(function (root) {
  "use strict";

  const SLOT_HEADER_HEIGHT = 30;
  const SLOT_GAP = 10;
  const STAGE_PADDING = 12;
  const DEFAULT_ASPECT = 9 / 19.5;
  const BASE_ZOOM_HEIGHT = 640;

  const ZOOM_PRESETS = ["fit", "50", "75", "100", "125", "150", "fill"];

  function safeAspect(item) {
    const w = Number(item && item.screen_width);
    const h = Number(item && item.screen_height);
    if (w > 100 && h > 100) {
      // Support both tall portrait phones (~0.43) and wide landscape phones (~2.35)
      return Math.max(0.35, Math.min(2.6, w / h));
    }
    return DEFAULT_ASPECT;
  }

  /**
   * Compute optimal multi-phone slot geometry inside the workspace stage.
   * Respects each device's live portrait or landscape orientation.
   */
  function computeWorkspaceLayout(stageWidth, stageHeight, items, zoomMode) {
    const count = Array.isArray(items) ? items.length : 0;
    const mode = ZOOM_PRESETS.includes(String(zoomMode)) ? String(zoomMode) : "fit";
    const availW = Math.max(220, Math.floor(stageWidth));
    const availH = Math.max(220, Math.floor(stageHeight));

    if (count === 0) {
      return {
        mode,
        cols: 1,
        rows: 1,
        scrollable: false,
        slots: [],
      };
    }

    const pad = mode === "fill" ? 6 : STAGE_PADDING;
    const gap = mode === "fill" ? 6 : SLOT_GAP;
    const innerW = Math.max(180, availW - pad * 2);
    const innerH = Math.max(180, availH - pad * 2);

    if (mode === "fit" || mode === "fill") {
      let best = null;
      const maxCols = Math.min(count, 6);

      for (let cols = 1; cols <= maxCols; cols += 1) {
        const rows = Math.ceil(count / cols);
        const cellW = (innerW - gap * (cols - 1)) / cols;
        const cellH = (innerH - gap * (rows - 1)) / rows;
        const maxVideoH = cellH - SLOT_HEADER_HEIGHT;
        if (cellW < 80 || maxVideoH < 80) continue;

        let totalArea = 0;
        const candidateSlots = [];

        for (let i = 0; i < count; i += 1) {
          const aspect = safeAspect(items[i]);
          let videoH = maxVideoH;
          let videoW = videoH * aspect;
          if (videoW > cellW) {
            videoW = cellW;
            videoH = videoW / aspect;
          }
          videoW = Math.max(80, Math.floor(videoW));
          videoH = Math.max(80, Math.floor(videoH));
          totalArea += videoW * videoH;
          candidateSlots.push({
            id: items[i].id,
            serial: items[i].serial,
            landscape: aspect > 1.05,
            videoWidth: videoW,
            videoHeight: videoH,
            cardWidth: videoW,
            cardHeight: videoH + SLOT_HEADER_HEIGHT,
            scalePct: Math.round((Math.max(videoW, videoH) / BASE_ZOOM_HEIGHT) * 100),
          });
        }

        if (!best || totalArea > best.totalArea) {
          best = { cols, rows, totalArea, slots: candidateSlots };
        }
      }

      if (!best) {
        const fallbackW = Math.max(120, Math.floor(innerW));
        const fallbackH = Math.max(120, Math.floor(innerH - SLOT_HEADER_HEIGHT));
        best = {
          cols: 1,
          rows: count,
          slots: items.map((item) => ({
            id: item.id,
            serial: item.serial,
            landscape: safeAspect(item) > 1.05,
            videoWidth: fallbackW,
            videoHeight: fallbackH,
            cardWidth: fallbackW,
            cardHeight: fallbackH + SLOT_HEADER_HEIGHT,
            scalePct: Math.round((Math.max(fallbackW, fallbackH) / BASE_ZOOM_HEIGHT) * 100),
          })),
        };
      }

      return {
        mode,
        cols: best.cols,
        rows: best.rows,
        scrollable: false,
        gap,
        padding: pad,
        slots: best.slots,
      };
    }

    // Fixed percentage zoom mode (50%, 75%, 100%, 125%, 150%)
    const pct = Number(mode);
    const refLongSide = Math.max(480, Math.min(Math.max(innerW, innerH - SLOT_HEADER_HEIGHT), BASE_ZOOM_HEIGHT));
    const targetLongSide = Math.max(180, Math.round((refLongSide * pct) / 100));

    const slots = items.map((item) => {
      const aspect = safeAspect(item);
      let videoW;
      let videoH;
      if (aspect > 1.05) {
        // Landscape phone: scale by width so landscape frame stays generous
        videoW = targetLongSide;
        videoH = Math.round(videoW / aspect);
      } else {
        videoH = targetLongSide;
        videoW = Math.round(videoH * aspect);
      }
      if (videoW > innerW) {
        videoW = Math.max(120, innerW);
        videoH = Math.round(videoW / aspect);
      }
      return {
        id: item.id,
        serial: item.serial,
        landscape: aspect > 1.05,
        videoWidth: videoW,
        videoHeight: videoH,
        cardWidth: videoW,
        cardHeight: videoH + SLOT_HEADER_HEIGHT,
        scalePct: pct,
      };
    });

    const maxCardW = Math.max(...slots.map((s) => s.cardWidth));
    const cols = Math.max(1, Math.min(count, Math.floor((innerW + gap) / (maxCardW + gap))));
    const rows = Math.ceil(count / cols);

    return {
      mode,
      cols,
      rows,
      scrollable: true,
      gap,
      padding: pad,
      slots,
    };
  }

  const exported = {
    SLOT_HEADER_HEIGHT,
    ZOOM_PRESETS,
    computeWorkspaceLayout,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
  } else {
    root.PhoneControlLayout = exported;
  }
})(typeof window !== "undefined" ? window : globalThis);
