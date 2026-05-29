// Owner/admin helpers: copy share link + dropzone file selection.
function copyShare() {
  const el = document.getElementById('shareUrl');
  el.select();
  navigator.clipboard.writeText(el.value).then(() => {
    const btn = event.target;
    const old = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => (btn.textContent = old), 1500);
  });
}

document.querySelectorAll('[data-dropzone]').forEach((zone) => {
  const input = zone.querySelector('input[type=file]');
  const count = zone.querySelector('[data-count]');
  const dz = zone.classList.contains('dropzone') ? zone : zone.querySelector('.dropzone') || zone;

  function show() {
    if (count && input.files.length) {
      count.textContent = input.files.length + ' file(s) selected';
    }
  }
  input.addEventListener('change', show);

  ['dragenter', 'dragover'].forEach((e) =>
    dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.add('drag'); })
  );
  ['dragleave', 'drop'].forEach((e) =>
    dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.remove('drag'); })
  );
  dz.addEventListener('drop', (ev) => {
    input.files = ev.dataTransfer.files;
    show();
  });
});
