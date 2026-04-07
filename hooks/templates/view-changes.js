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
// Auto-expand directories containing changed files in explorer
document.querySelectorAll('#sidebar-explorer .tree-modified, #sidebar-explorer .tree-untracked, #sidebar-explorer .tree-added, #sidebar-explorer .tree-deleted, #sidebar-explorer .tree-renamed').forEach(el => {
  let parent = el.parentElement;
  while (parent) {
    if (parent.classList && parent.classList.contains('tree-dir')) {
      parent.classList.add('open');
    }
    parent = parent.parentElement;
  }
});
function clearActiveNav() {
  document.querySelectorAll('.tree-active').forEach(el => el.classList.remove('tree-active'));
}
// --- Activity bar panel switching ---
function switchPanel(panel) {
  var scmPanel = document.getElementById('sidebar-scm');
  var explorerPanel = document.getElementById('sidebar-explorer');
  var scmBtn = document.getElementById('actbtn-scm');
  var explorerBtn = document.getElementById('actbtn-explorer');
  if (panel === 'scm') {
    scmPanel.style.display = '';
    explorerPanel.style.display = 'none';
    scmBtn.classList.add('active');
    explorerBtn.classList.remove('active');
  } else {
    scmPanel.style.display = 'none';
    explorerPanel.style.display = '';
    scmBtn.classList.remove('active');
    explorerBtn.classList.add('active');
  }
}
// --- Show full file toggle ---
function toggleFullFile(idx) {
  var diffView = document.getElementById('diff-view-' + idx);
  var fullView = document.getElementById('full-view-' + idx);
  if (!diffView || !fullView) return;
  var btn = document.querySelector('#file-' + idx + ' .diff-toggle');
  if (fullView.style.display === 'none') {
    diffView.style.display = 'none';
    fullView.style.display = '';
    if (btn) btn.textContent = 'Show changes only';
  } else {
    diffView.style.display = '';
    fullView.style.display = 'none';
    if (btn) btn.textContent = 'Show full file';
  }
}
// --- Collapse/expand all ---
var allCollapsed = false;
function toggleCollapseAll() {
  allCollapsed = !allCollapsed;
  document.querySelectorAll('.main details').forEach(det => {
    det.open = !allCollapsed;
  });
  var btn = document.getElementById('collapse-all-btn');
  if (btn) btn.title = allCollapsed ? 'Expand all' : 'Collapse all';
  if (btn) btn.classList.toggle('is-collapsed', allCollapsed);
}
// --- Resizable sidebar ---
(function() {
  var handle = document.getElementById('resize-handle');
  var sidebar = document.querySelector('.sidebar');
  if (!handle || !sidebar) return;
  var dragging = false;
  handle.addEventListener('mousedown', function(e) {
    e.preventDefault();
    dragging = true;
    handle.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  });
  document.addEventListener('mousemove', function(e) {
    if (!dragging) return;
    var w = Math.max(120, Math.min(e.clientX, window.innerWidth - 200));
    sidebar.style.width = w + 'px';
  });
  document.addEventListener('mouseup', function() {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();
// Scroll to first changed file on load
(function() {
  var first = document.querySelector('.main details[open]');
  if (first) first.scrollIntoView({block: 'start', behavior: 'auto'});
})();
