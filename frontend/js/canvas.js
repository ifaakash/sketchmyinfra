/**
 * Diagram canvas: fit-to-screen, zoom and pan for #diagram-image.
 *
 * The viewport (#diagram-viewport) has a fixed size and never scrolls. The
 * diagram sits in #diagram-stage at its natural size, and one CSS transform
 * moves and scales it:  translate(x, y) scale(s)  with transform-origin 0 0.
 * So a point p on the diagram lands at  x + p * s  in viewport pixels.
 *
 * Input:
 *   drag (mouse / one finger)          pan
 *   wheel / trackpad two-finger scroll  pan
 *   Ctrl/⌘ + wheel, trackpad pinch      zoom around the cursor
 *   two-finger pinch (touch)            zoom around the fingers
 *   double-click                        100% at that point, or back to fit
 *   keys: 0 fit · 1 100% · + / − zoom · f full screen
 */
(function () {
  const MIN_SCALE = 0.05;
  const MAX_SCALE = 8;
  const STEP = 1.25;
  // Space kept clear around a fitted diagram: zoom controls top-right,
  // rating pill bottom-centre.
  const PAD = { top: 60, right: 24, bottom: 72, left: 24 };

  // Clicks on overlays (zoom controls, rating pill) must not start a pan
  const NO_PAN = 'button, input, form, a, #rating-row, [role="toolbar"]';

  const view = { scale: 1, x: 0, y: 0 };
  let fitted = true;   // true until the user zooms/pans; resize re-fits only then
  let vp, stage, img, label;

  const clamp = (s) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

  function apply() {
    stage.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
    if (label) label.textContent = `${Math.round(view.scale * 100)}%`;
  }

  // Size of the diagram card at scale 1 (image + its padding and border)
  function contentSize() {
    return { w: img.offsetWidth, h: img.offsetHeight };
  }

  function fit() {
    const box = vp.getBoundingClientRect();
    const { w, h } = contentSize();
    if (!w || !h || !box.width || !box.height) return; // hidden pane: ResizeObserver retries
    const availW = Math.max(box.width - PAD.left - PAD.right, 40);
    const availH = Math.max(box.height - PAD.top - PAD.bottom, 40);
    // Never upscale past 100%: small diagrams stay crisp at their real size
    view.scale = clamp(Math.min(availW / w, availH / h, 1));
    view.x = PAD.left + (availW - w * view.scale) / 2;
    view.y = PAD.top + (availH - h * view.scale) / 2;
    fitted = true;
    apply();
  }

  /**
   * Zoom so the diagram point under (cx, cy) stays under (cx, cy).
   * Before: cx = x + p*s  ->  p = (cx - x) / s
   * After:  cx = x' + p*s' ->  x' = cx - (cx - x) * s'/s
   */
  function zoomTo(scale, cx, cy) {
    const next = clamp(scale);
    const ratio = next / view.scale;
    view.x = cx - (cx - view.x) * ratio;
    view.y = cy - (cy - view.y) * ratio;
    view.scale = next;
    fitted = false;
    apply();
  }

  function centre() {
    const box = vp.getBoundingClientRect();
    return [box.width / 2, box.height / 2];
  }

  function zoomBy(factor) {
    zoomTo(view.scale * factor, ...centre());
  }

  function panBy(dx, dy) {
    view.x += dx;
    view.y += dy;
    fitted = false;
    apply();
  }

  function localPoint(e) {
    const box = vp.getBoundingClientRect();
    return [e.clientX - box.left, e.clientY - box.top];
  }

  // ----- Wheel: scroll pans, Ctrl/⌘ (and trackpad pinch, which sets ctrlKey) zooms -----
  function onWheel(e) {
    e.preventDefault();
    // deltaMode 1 = lines (Firefox mouse wheels); normalise to pixels
    const unit = e.deltaMode === 1 ? 16 : 1;
    if (e.ctrlKey || e.metaKey) {
      // A mouse-wheel notch is ~100px, a trackpad pinch event ~1-10px.
      // Clamping keeps a notch at ~1.2x while pinch stays smooth.
      const delta = Math.max(-50, Math.min(50, e.deltaY * unit));
      zoomTo(view.scale * Math.exp(-delta * 0.004), ...localPoint(e));
    } else {
      panBy(-e.deltaX * unit, -e.deltaY * unit);
    }
  }

  // ----- Pointers: one = pan, two = pinch -----
  const pointers = new Map();
  let pinch = null; // { dist, scale, mid }

  function pinchState() {
    const [a, b] = [...pointers.values()];
    return {
      dist: Math.hypot(a.x - b.x, a.y - b.y),
      mid: [(a.x + b.x) / 2, (a.y + b.y) / 2],
    };
  }

  function onPointerDown(e) {
    if (e.button !== 0 || e.target.closest(NO_PAN)) return;
    vp.setPointerCapture(e.pointerId);
    const [x, y] = localPoint(e);
    pointers.set(e.pointerId, { x, y });
    if (pointers.size === 2) {
      const s = pinchState();
      pinch = { dist: s.dist, scale: view.scale, mid: s.mid };
    }
    vp.classList.add('is-panning');
  }

  function onPointerMove(e) {
    const p = pointers.get(e.pointerId);
    if (!p) return;
    const [x, y] = localPoint(e);
    if (pointers.size === 1) {
      panBy(x - p.x, y - p.y);
      p.x = x; p.y = y;
      return;
    }
    p.x = x; p.y = y;
    if (pinch && pointers.size === 2) {
      const s = pinchState();
      // Pan with the fingers' midpoint, then zoom around it
      panBy(s.mid[0] - pinch.mid[0], s.mid[1] - pinch.mid[1]);
      pinch.mid = s.mid;
      zoomTo(pinch.scale * (s.dist / pinch.dist), ...s.mid);
    }
  }

  function onPointerUp(e) {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (pointers.size === 0) vp.classList.remove('is-panning');
  }

  function onDoubleClick(e) {
    if (e.target.closest(NO_PAN)) return;
    if (Math.abs(view.scale - 1) > 0.01) zoomTo(1, ...localPoint(e));
    else fit();
  }

  // ----- Keyboard: only when the diagram is on screen and the user isn't typing -----
  function onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest?.('input, textarea, select, [contenteditable="true"]')) return;
    if (!vp.offsetParent) return; // diagram pane hidden
    const actions = {
      '0': fit,
      '1': () => zoomTo(1, ...centre()),
      '+': () => zoomBy(STEP),
      '=': () => zoomBy(STEP),
      '-': () => zoomBy(1 / STEP),
      'f': toggleFullscreen,
    };
    const action = actions[e.key];
    if (!action) return;
    e.preventDefault();
    action();
  }

  function toggleFullscreen() {
    if (!document.fullscreenEnabled) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else vp.requestFullscreen?.().catch(() => {});
  }

  function init() {
    vp = document.getElementById('diagram-viewport');
    stage = document.getElementById('diagram-stage');
    img = document.getElementById('diagram-image');
    label = document.getElementById('zoom-level');
    if (!vp || !stage || !img) return;

    // Every new diagram (generate, re-render, history, claim) starts fitted
    img.addEventListener('load', fit);

    vp.addEventListener('wheel', onWheel, { passive: false });
    vp.addEventListener('pointerdown', onPointerDown);
    vp.addEventListener('pointermove', onPointerMove);
    vp.addEventListener('pointerup', onPointerUp);
    vp.addEventListener('pointercancel', onPointerUp);
    vp.addEventListener('dblclick', onDoubleClick);
    document.addEventListener('keydown', onKey);

    // Pane resized, shown (was 0x0 while hidden) or full screen toggled:
    // keep it fitted unless the user has moved it themselves.
    new ResizeObserver(() => { if (fitted) fit(); }).observe(vp);

    document.getElementById('btn-zoom-in')?.addEventListener('click', () => zoomBy(STEP));
    document.getElementById('btn-zoom-out')?.addEventListener('click', () => zoomBy(1 / STEP));
    document.getElementById('btn-zoom-reset')?.addEventListener('click', () => zoomTo(1, ...centre()));
    document.getElementById('btn-zoom-fit')?.addEventListener('click', fit);

    const fsBtn = document.getElementById('btn-fullscreen');
    if (fsBtn && document.fullscreenEnabled) {
      fsBtn.classList.remove('hidden');
      fsBtn.classList.add('grid');
      fsBtn.addEventListener('click', toggleFullscreen);
    }
  }

  window.diagramCanvas = { fit };
  document.addEventListener('DOMContentLoaded', init);
})();
