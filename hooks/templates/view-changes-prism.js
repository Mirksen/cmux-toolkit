(function() {
  // Trigger Prism highlighting before post-processing diff blocks
  Prism.highlightAll(false);

  // Helper: split highlighted HTML by newlines, preserving open span tags across lines
  function splitHighlightedLines(html) {
    var lines = html.split('\n');
    var result = [];
    var openSpans = [];
    for (var i = 0; i < lines.length; i++) {
      // Prepend any open spans from previous line
      var prefix = openSpans.join('');
      var line = lines[i];
      // Track open/close spans in this line
      var tags = line.match(/<\/?span[^>]*>/g) || [];
      for (var j = 0; j < tags.length; j++) {
        if (tags[j].indexOf('</') === 0) {
          openSpans.pop();
        } else {
          openSpans.push(tags[j]);
        }
      }
      // Close any open spans at end of line
      var suffix = '';
      for (var k = openSpans.length - 1; k >= 0; k--) { suffix += '</span>'; }
      result.push(prefix + line + suffix);
    }
    return result;
  }

  // Helper: highlight deleted lines using Prism if language is available
  function highlightDeleted(lines, lang) {
    if (!lang || !Prism.languages[lang]) return lines.map(function(l) {
      var d = document.createElement('span');
      d.textContent = l;
      return d.innerHTML;
    });
    var code = lines.join('\n');
    var highlighted = Prism.highlight(code, Prism.languages[lang], lang);
    return splitHighlightedLines(highlighted);
  }

  // Process new-file blocks: wrap every line in diff-line
  document.querySelectorAll('code[data-diff-type="new-file"]').forEach(function(codeEl) {
    var highlighted = codeEl.innerHTML;
    var lines = splitHighlightedLines(highlighted);
    codeEl.innerHTML = lines.map(function(l) {
      return '<span class="line diff-line">' + l + '</span>';
    }).join('\n');
  });

  // Process modified-file blocks: build collapsed + full views
  document.querySelectorAll('code[data-diff-idx]').forEach(function(codeEl) {
    var idx = parseInt(codeEl.getAttribute('data-diff-idx'));
    var metaScript = document.getElementById('diff-meta-' + idx);
    if (!metaScript) return;
    var meta = JSON.parse(metaScript.textContent);
    var types = meta.types;
    var deleted = meta.deleted;
    var CONTEXT = meta.context;
    var lang = '';
    var cls = codeEl.className || '';
    var m = cls.match(/language-(\w+)/);
    if (m) lang = m[1];

    var highlighted = codeEl.innerHTML;
    var hLines = splitHighlightedLines(highlighted);

    // Build all lines with diff markers (matching original Python logic)
    var allLines = [];
    var allTypes = [];
    for (var i = 0; i < hLines.length; i++) {
      if (deleted[String(i)]) {
        var delHL = highlightDeleted(deleted[String(i)], lang);
        for (var d = 0; d < delHL.length; d++) {
          allLines.push('<span class="line diff-del-line">' + delHL[d] + '</span>');
          allTypes.push('del');
        }
      }
      var cls = (types[i] === 'new') ? 'line diff-line' : 'line';
      allLines.push('<span class="' + cls + '">' + hLines[i] + '</span>');
      allTypes.push(types[i]);
    }

    // Build collapsed view
    var important = new Set();
    for (var i = 0; i < allTypes.length; i++) {
      if (allTypes[i] === 'new' || allTypes[i] === 'del') {
        for (var j = Math.max(0, i - CONTEXT); j < Math.min(allTypes.length, i + CONTEXT + 1); j++) {
          important.add(j);
        }
      }
    }
    var collapsedLines = [];
    var lastShown = -1;
    for (var i = 0; i < allLines.length; i++) {
      if (important.has(i)) {
        if (lastShown >= 0 && i > lastShown + 1) {
          var skipped = i - lastShown - 1;
          collapsedLines.push('<span class="line-skip">--- ' + skipped + ' lines hidden ---</span>');
        }
        collapsedLines.push(allLines[i]);
        lastShown = i;
      }
    }
    if (lastShown < allLines.length - 1) {
      var skipped = allLines.length - lastShown - 1;
      collapsedLines.push('<span class="line-skip">--- ' + skipped + ' lines hidden ---</span>');
    }

    // Populate collapsed and full divs (include language class so Prism CSS selectors match)
    var langCls = lang ? ' class="language-' + lang + '"' : '';
    var collapsedDiv = document.getElementById('diff-collapsed-' + idx);
    var fullDiv = document.getElementById('diff-full-' + idx);
    if (collapsedDiv) collapsedDiv.innerHTML = '<pre><code' + langCls + '>' + collapsedLines.join('\n') + '</code></pre>';
    if (fullDiv) fullDiv.innerHTML = '<pre><code' + langCls + '>' + allLines.join('\n') + '</code></pre>';
  });
})();
