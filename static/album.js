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

// Lightbox with prev/next (buttons, arrow keys, swipe)
const lb = document.getElementById('lightbox');
const lbImg = document.getElementById('lbImg');
const lbDl = document.getElementById('lbDownload');
const items = Array.from(document.querySelectorAll('.g-item'));
let idx = 0;

function render() {
  const a = items[idx];
  if (!a) return;
  lbImg.src = a.dataset.full;
  lbDl.href = a.dataset.orig;
}
function openLb(i) {
  idx = i;
  render();
  lb.hidden = false;
  document.body.style.overflow = 'hidden';
}
function closeLb() { lb.hidden = true; lbImg.src = ''; document.body.style.overflow = ''; }
function step(delta) {
  if (items.length < 2) return;
  idx = (idx + delta + items.length) % items.length;  // wrap around
  render();
}

items.forEach((a, i) => {
  a.addEventListener('click', (e) => { e.preventDefault(); openLb(i); });
});
document.getElementById('lbClose').addEventListener('click', closeLb);
const prevBtn = document.getElementById('lbPrev');
const nextBtn = document.getElementById('lbNext');
if (prevBtn) prevBtn.addEventListener('click', (e) => { e.stopPropagation(); step(-1); });
if (nextBtn) nextBtn.addEventListener('click', (e) => { e.stopPropagation(); step(1); });

lb.addEventListener('click', (e) => { if (e.target === lb) closeLb(); });
document.addEventListener('keydown', (e) => {
  if (lb.hidden) return;
  if (e.key === 'Escape') closeLb();
  else if (e.key === 'ArrowLeft') step(-1);
  else if (e.key === 'ArrowRight') step(1);
});

// Touch swipe (horizontal)
let touchX = null, touchY = null;
lb.addEventListener('touchstart', (e) => {
  touchX = e.changedTouches[0].clientX;
  touchY = e.changedTouches[0].clientY;
}, { passive: true });
lb.addEventListener('touchend', (e) => {
  if (touchX === null) return;
  const dx = e.changedTouches[0].clientX - touchX;
  const dy = e.changedTouches[0].clientY - touchY;
  if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) step(dx < 0 ? 1 : -1);
  touchX = touchY = null;
}, { passive: true });
