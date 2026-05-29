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

// Lightbox
const lb = document.getElementById('lightbox');
const lbImg = document.getElementById('lbImg');
const lbDl = document.getElementById('lbDownload');
document.querySelectorAll('.g-item').forEach((a) => {
  a.addEventListener('click', (e) => {
    e.preventDefault();
    lbImg.src = a.dataset.full;
    lbDl.href = a.dataset.orig;
    lb.hidden = false;
    document.body.style.overflow = 'hidden';
  });
});
function closeLb() { lb.hidden = true; lbImg.src = ''; document.body.style.overflow = ''; }
document.getElementById('lbClose').addEventListener('click', closeLb);
lb.addEventListener('click', (e) => { if (e.target === lb) closeLb(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !lb.hidden) closeLb(); });
