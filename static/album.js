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

// Touch drag: the photo tracks the finger; resists at the ends.
let sx = null, sy = null, dragging = false, locked = false;
stage.addEventListener('touchstart', (e) => {
  if (animating) { sx = null; return; }
  const t = e.changedTouches[0];
  sx = t.clientX; sy = t.clientY; dragging = false; locked = false;
}, { passive: true });

stage.addEventListener('touchmove', (e) => {
  if (sx === null || animating) return;
  const t = e.changedTouches[0];
  const dx = t.clientX - sx, dy = t.clientY - sy;
  if (!locked) {
    if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
    if (Math.abs(dy) > Math.abs(dx)) { sx = null; return; }  // vertical → ignore
    locked = true; dragging = true;
  }
  const hasPrev = idx > 0, hasNext = idx < items.length - 1;
  let eff = dx;
  if ((dx > 0 && !hasPrev) || (dx < 0 && !hasNext)) eff = dx * 0.28;  // resist
  translate(-100, eff, false);
}, { passive: true });

stage.addEventListener('touchend', (e) => {
  if (sx === null) return;
  const dx = e.changedTouches[0].clientX - sx;
  const wasDragging = dragging;
  sx = sy = null; dragging = false; locked = false;
  if (!wasDragging) return;
  const threshold = Math.min(80, stage.clientWidth * 0.18);
  const hasPrev = idx > 0, hasNext = idx < items.length - 1;
  if (dx <= -threshold && hasNext) slideTo(1);
  else if (dx >= threshold && hasPrev) slideTo(-1);
  else translate(-100, 0, true);  // snap back
}, { passive: true });
