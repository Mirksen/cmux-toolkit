function openFile(idx) {
  // Hide any open viewer sections
  document.querySelectorAll('.viewer-section').forEach(el => el.style.display = 'none');
  const details = document.querySelectorAll('.main details');
  if (details[idx]) {
    var wasOpen = details[idx].open;
    details[idx].open = !wasOpen;
    if (!wasOpen) {
      details[idx].scrollIntoView({block: 'start', behavior: 'smooth'});
    }
  }
  clearActiveNav();
  if (details[idx] && details[idx].open) {
    const items = document.querySelectorAll('[onclick*="openFile(' + idx + ')"]');
    items.forEach(el => el.classList.add('tree-active'));
  }
}
// Tree directory toggles
document.querySelectorAll('.tree-dir > .tree-toggle').forEach(el => {
  el.addEventListener('click', () => el.parentElement.classList.toggle('open'));
});
// Sync nav highlight when collapsible is toggled directly
document.querySelectorAll('.main details').forEach((det, idx) => {
  det.addEventListener('toggle', () => {
    const navItems = document.querySelectorAll('[onclick*="openFile(' + idx + ')"]');
    if (det.open) {
      clearActiveNav();
      navItems.forEach(el => el.classList.add('tree-active'));
    } else {
      navItems.forEach(el => el.classList.remove('tree-active'));
    }
  });
});
// Auto-expand directories containing changed files
document.querySelectorAll('.tree-modified, .tree-untracked, .tree-added, .tree-deleted, .tree-renamed').forEach(el => {
  let parent = el.parentElement;
  while (parent) {
    if (parent.classList && parent.classList.contains('tree-dir')) {
      parent.classList.add('open');
    }
    parent = parent.parentElement;
  }
});
function toggleFullFile(idx) {
  const collapsed = document.getElementById('diff-collapsed-' + idx);
  const full = document.getElementById('diff-full-' + idx);
  if (!collapsed || !full) return;
  const btn = document.querySelector('[onclick*="toggleFullFile(' + idx + ')"]');
  if (full.style.display === 'none') {
    collapsed.style.display = 'none';
    full.style.display = '';
    if (btn) btn.textContent = 'Show changes only';
  } else {
    collapsed.style.display = '';
    full.style.display = 'none';
    if (btn) btn.textContent = 'Show full file';
  }
}
function openViewer(idx) {
  var viewer = document.getElementById('viewer-' + idx);
  if (!viewer) return;
  var wasVisible = viewer.style.display !== 'none';
  document.querySelectorAll('.viewer-section').forEach(function(el) { el.style.display = 'none'; });
  clearActiveNav();
  if (!wasVisible) {
    viewer.style.display = '';
    viewer.scrollIntoView({block: 'start', behavior: 'smooth'});
    var item = document.querySelector('[onclick*="openViewer(' + idx + ')"]');
    if (item) item.classList.add('tree-active');
  }
}
function clearActiveNav() {
  document.querySelectorAll('.tree-active').forEach(el => el.classList.remove('tree-active'));
}
