// Public album: dropzone selection + lightbox with download.
document.querySelectorAll('[data-dropzone]').forEach((form) => {
  const input = form.querySelector('input[type=file]');
  const count = form.querySelector('[data-count]');
  const dz = form.querySelector('.dropzone');

  function show() {
    if (count && input.files.length) count.textContent = input.files.length + ' file(s) ready to upload';
  }
  input.addEventListener('change', show);
  ['dragenter', 'dragover'].forEach((e) =>
    dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.add('drag'); })
  );
  ['dragleave', 'drop'].forEach((e) =>
    dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.remove('drag'); })
  );
  dz.addEventListener('drop', (ev) => { input.files = ev.dataTransfer.files; show(); });
});

// Lightbox: tap a photo, then swipe (touch) or use the arrow keys to move.
// A 3-slide track [prev | current | next] is translated; dragging follows the
// finger and, at the ends (no neighbour), resists like a rubber band.
const lb = document.getElementById('lightbox');
const stage = document.getElementById('lbStage');
const track = document.getElementById('lbTrack');
const lbDl = document.getElementById('lbDownload');
const slides = Array.from(track.querySelectorAll('.lb-slide img')); // [prev, cur, next]
const items = Array.from(document.querySelectorAll('.g-item'));
let idx = 0;
let animating = false;

// Pinch-zoom state (mobile): the centre slide's <img> is scaled/translated on
// top of the navigation track. While zoomed, one finger pans instead of swiping.
const MAX_ZOOM = 4;
let zoom = 1, panX = 0, panY = 0;

function setSlide(img, i) {
  if (i >= 0 && i < items.length) {
    img.src = items[i].dataset.full;
    img.style.visibility = '';
  } else {
    img.removeAttribute('src');
    img.style.visibility = 'hidden';  // empty edge slide — nothing to drag in
  }
}

// Every transform keeps the identical translateX(calc(P% + Npx)) shape so the
// browser interpolates smoothly between a drag position and the settle target.
function translate(pct, px, animate) {
  track.style.transition = animate ? 'transform .28s ease' : 'none';
  track.style.transform = 'translateX(calc(' + pct + '% + ' + px + 'px))';
}

function buildWindow() {
  setSlide(slides[0], idx - 1);
  setSlide(slides[1], idx);
  setSlide(slides[2], idx + 1);
  if (items[idx]) lbDl.href = items[idx].dataset.orig;
  translate(-100, 0, false);   // recentre on the middle slide, no animation
  void track.offsetWidth;      // flush reflow so the next drag animates correctly
  resetZoom(false);            // a new photo always starts un-zoomed
}

function openLb(i) {
  idx = i;
  buildWindow();
  lb.hidden = false;
  document.body.style.overflow = 'hidden';
}
function closeLb() {
  lb.hidden = true;
  document.body.style.overflow = '';
  slides.forEach((img) => img.removeAttribute('src'));
}

// Animate to a neighbour, then recentre. finishSlide is idempotent so the
// transitionend handler and the safety timeout can never double-commit.
function slideTo(delta) {
  if (animating) return;
  const target = idx + delta;
  if (target < 0 || target >= items.length) return;  // no wrap; nothing to show
  animating = true;
  let settled = false;
  function finishSlide() {
    if (settled) return;
    settled = true;
    track.removeEventListener('transitionend', onEnd);
    idx = target;
    buildWindow();
    animating = false;
  }
  function onEnd(e) { if (e.propertyName === 'transform') finishSlide(); }
  track.addEventListener('transitionend', onEnd);
  setTimeout(finishSlide, 400);          // fallback if transitionend doesn't fire
  translate(delta > 0 ? -200 : 0, 0, true);
}

items.forEach((a, i) => {
  a.addEventListener('click', (e) => { e.preventDefault(); openLb(i); });
});
document.getElementById('lbClose').addEventListener('click', closeLb);
lb.addEventListener('click', (e) => { if (e.target === lb) closeLb(); });

document.addEventListener('keydown', (e) => {
  if (lb.hidden) return;
  if (e.key === 'Escape') closeLb();
  else if (e.key === 'ArrowLeft') slideTo(-1);
  else if (e.key === 'ArrowRight') slideTo(1);
});

// --- Pinch-zoom helpers ---------------------------------------------------
// The centre image carries its own transform = translate(pan) scale(zoom).
function applyZoom(animate) {
  slides[1].style.transition = animate ? 'transform .25s ease' : 'none';
  slides[1].style.transform =
    'translate(' + panX + 'px,' + panY + 'px) scale(' + zoom + ')';
}
function resetZoom(animate) { zoom = 1; panX = 0; panY = 0; applyZoom(animate); }

// Keep the (scaled) image from being dragged past the stage edges.
function clampPan() {
  const sw = stage.clientWidth, sh = stage.clientHeight;
  const iw = slides[1].offsetWidth * zoom, ih = slides[1].offsetHeight * zoom;
  const maxX = Math.max(0, (iw - sw) / 2), maxY = Math.max(0, (ih - sh) / 2);
  panX = Math.max(-maxX, Math.min(maxX, panX));
  panY = Math.max(-maxY, Math.min(maxY, panY));
}
// Touch coords relative to the stage centre (the image's transform origin).
function relCenter(x, y) {
  const r = stage.getBoundingClientRect();
  return { x: x - (r.left + r.width / 2), y: y - (r.top + r.height / 2) };
}
function touchDist(ts) {
  return Math.hypot(ts[0].clientX - ts[1].clientX, ts[0].clientY - ts[1].clientY);
}
function touchMid(ts) {
  return relCenter((ts[0].clientX + ts[1].clientX) / 2,
                   (ts[0].clientY + ts[1].clientY) / 2);
}

// Double-tap toggles between 1× and 2×, zooming toward the tapped point.
function toggleZoom(clientX, clientY) {
  if (zoom > 1) { resetZoom(true); return; }
  const f = relCenter(clientX, clientY);
  zoom = 2; panX = -f.x; panY = -f.y;   // keep tapped point under the finger
  clampPan(); applyZoom(true);
}

// --- Touch gestures: swipe (zoom 1×) · pinch · pan (zoomed) · double-tap ---
let sx = null, sy = null, dragging = false, locked = false;   // swipe
let panning = false, pStartX = 0, pStartY = 0, pBaseX = 0, pBaseY = 0;  // pan
let pinching = false, pinDist = 0, pinZoom = 1, pinMx = 0, pinMy = 0, pinPanX = 0, pinPanY = 0;
let multiTouch = false, downX = 0, downY = 0, downT = 0;      // tap bookkeeping
let lastTapT = 0, lastTapX = 0, lastTapY = 0;

function startPan(t) {
  panning = true; sx = null;
  pStartX = t.clientX; pStartY = t.clientY; pBaseX = panX; pBaseY = panY;
}

stage.addEventListener('touchstart', (e) => {
  if (e.touches.length >= 2) {            // begin pinch
    pinching = true; multiTouch = true; panning = false; sx = null; dragging = false; locked = false;
    pinDist = touchDist(e.touches); pinZoom = zoom;
    const m = touchMid(e.touches); pinMx = m.x; pinMy = m.y; pinPanX = panX; pinPanY = panY;
    translate(-100, 0, false);            // keep the nav track centred under the photo
    e.preventDefault();
    return;
  }
  const t = e.touches[0];
  downX = t.clientX; downY = t.clientY; downT = Date.now();
  if (zoom > 1) { startPan(t); return; }  // zoomed → one finger pans
  if (animating) { sx = null; return; }
  sx = t.clientX; sy = t.clientY; dragging = false; locked = false;
}, { passive: false });

stage.addEventListener('touchmove', (e) => {
  if (pinching && e.touches.length >= 2) {
    e.preventDefault();
    let Z = pinZoom * (touchDist(e.touches) / pinDist);
    Z = Math.max(1, Math.min(MAX_ZOOM, Z));
    const m = touchMid(e.touches);
    panX = m.x - Z * (pinMx - pinPanX) / pinZoom;   // hold the focal point steady
    panY = m.y - Z * (pinMy - pinPanY) / pinZoom;
    zoom = Z; clampPan(); applyZoom(false);
    return;
  }
  if (panning) {
    e.preventDefault();
    const t = e.touches[0];
    panX = pBaseX + (t.clientX - pStartX); panY = pBaseY + (t.clientY - pStartY);
    clampPan(); applyZoom(false);
    return;
  }
  if (sx === null || animating) return;   // swipe (only when not zoomed)
  const t = e.changedTouches[0];
  const dx = t.clientX - sx, dy = t.clientY - sy;
  if (!locked) {
    if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
    if (Math.abs(dy) > Math.abs(dx)) { sx = null; return; }  // vertical → ignore
    locked = true; dragging = true;
  }
  e.preventDefault();
  const hasPrev = idx > 0, hasNext = idx < items.length - 1;
  let eff = dx;
  if ((dx > 0 && !hasPrev) || (dx < 0 && !hasNext)) eff = dx * 0.28;  // resist
  translate(-100, eff, false);
}, { passive: false });

// A clean tap (no drag, short, not part of a pinch); fires double-tap zoom.
function maybeTap(e) {
  if (multiTouch) return;
  const t = e.changedTouches[0], now = Date.now();
  if (now - downT > 300) { lastTapT = 0; return; }
  if (Math.abs(t.clientX - downX) > 12 || Math.abs(t.clientY - downY) > 12) { lastTapT = 0; return; }
  if (now - lastTapT < 300 && Math.abs(t.clientX - lastTapX) < 40 && Math.abs(t.clientY - lastTapY) < 40) {
    lastTapT = 0; toggleZoom(t.clientX, t.clientY);
  } else {
    lastTapT = now; lastTapX = t.clientX; lastTapY = t.clientY;
  }
}

stage.addEventListener('touchend', (e) => {
  if (pinching) {
    if (e.touches.length < 2) {
      pinching = false;
      if (zoom <= 1.02) resetZoom(true);
      else { clampPan(); applyZoom(true); if (e.touches.length === 1) startPan(e.touches[0]); }
    }
    if (e.touches.length === 0) multiTouch = false;
    return;
  }
  if (panning) {
    if (e.touches.length === 0) { panning = false; clampPan(); applyZoom(true); maybeTap(e); multiTouch = false; }
    return;
  }
  if (sx === null) {                       // a tap with no swipe in progress
    if (e.touches.length === 0) { maybeTap(e); multiTouch = false; }
    return;
  }
  const dx = e.changedTouches[0].clientX - sx;
  const wasDragging = dragging;
  sx = sy = null; dragging = false; locked = false;
  if (!wasDragging) { maybeTap(e); if (e.touches.length === 0) multiTouch = false; return; }
  const threshold = Math.min(80, stage.clientWidth * 0.18);
  const hasPrev = idx > 0, hasNext = idx < items.length - 1;
  if (dx <= -threshold && hasNext) slideTo(1);
  else if (dx >= threshold && hasPrev) slideTo(-1);
  else translate(-100, 0, true);  // snap back
  if (e.touches.length === 0) multiTouch = false;
}, { passive: false });
