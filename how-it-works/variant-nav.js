/* Previous/next switching inside one set of ten how-it-works variants: w1..w10 (round 1) or x1..x10 (round 2), chosen by the letter in the file name. */
(function () {
  var N = 10;
  var m = location.pathname.match(/\/([wx])(\d+)(?:\.html)?$/);
  var set = m ? m[1] : '';
  var cur = m ? parseInt(m[2], 10) : 0;
  if (!set || cur < 1 || cur > N) return;
  function file(n) { return set + (((n - 1 + N) % N) + 1) + '.html'; }
  function go(d) { location.href = file(cur + d); }

  var css = document.createElement('style');
  css.textContent =
    '#vnav{position:fixed;right:10px;bottom:10px;z-index:2147483000;display:flex;align-items:center;gap:2px;' +
    'padding:2px 4px;border-radius:999px;background:rgba(20,22,28,.88);color:#fff;border:1px solid rgba(255,255,255,.35);' +
    'font:600 13px/1 system-ui,-apple-system,"Segoe UI",sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.35)}' +
    '#vnav a{color:#fff;text-decoration:none;padding:6px 8px;border-radius:999px;display:inline-block}' +
    '#vnav a:hover{background:rgba(255,255,255,.2)}' +
    '#vnav a:focus-visible{outline:2px solid #fff;outline-offset:1px;box-shadow:0 0 0 4px #1a56db}' +
    '#vnav .a{font-size:17px;line-height:1}';
  document.head.appendChild(css);

  var nav = document.createElement('nav');
  nav.id = 'vnav';
  nav.setAttribute('aria-label', 'Switch variant');
  nav.innerHTML =
    '<a class="a" href="' + file(cur - 1) + '" rel="prev" aria-label="Previous variant">‹</a>' +
    '<a href="../" aria-label="Back to all variants">' + set + ' ' + cur + ' / ' + N + '</a>' +
    '<a class="a" href="' + file(cur + 1) + '" rel="next" aria-label="Next variant">›</a>';
  document.body.appendChild(nav);

  /* park in the first corner where it covers no text, link, control or picture at the top of the page */
  function clear() {
    var r = nav.getBoundingClientRect();
    var rails = document.querySelectorAll("#rail, #railnav");
    for (var k = 0; k < rails.length; k++) {
      var rr = rails[k].getBoundingClientRect();
      if (rr.width && rr.height && rr.left < r.right + 8 && rr.right > r.left - 8 && rr.top < r.bottom + 8 && rr.bottom > r.top - 8) return false;
    }
    var all = document.body.getElementsByTagName("*");
    for (var i = 0; i < all.length; i++) {
      var e = all[i];
      if (nav.contains(e) || /^(SCRIPT|STYLE|PATH|LINE|G|DEFS|MARKER)$/i.test(e.tagName)) continue;
      var leaf = !e.children.length || /^(A|BUTTON|SVG|IMG|CANVAS)$/i.test(e.tagName);
      if (!leaf) continue;
      if (!e.textContent.trim() && !/^(SVG|IMG|CANVAS|INPUT)$/i.test(e.tagName)) continue;
      var cs = getComputedStyle(e);
      if (cs.visibility === "hidden" || cs.display === "none" || cs.opacity === "0") continue;
      var q = e.getBoundingClientRect();
      /* a page-sized drawing (the map itself, a leader-line overlay) is not an obstacle: what is drawn on it is checked by its own text */
      if (/^(SVG|IMG|CANVAS)$/i.test(e.tagName) && q.width * q.height > 0.4 * innerWidth * innerHeight) continue;
      if (q.width && q.height && q.left < r.right && q.right > r.left && q.top < r.bottom && q.bottom > r.top) return false;
    }
    return true;
  }
  function place() {
    /* round 2 (x): first the empty middle of the top bar, which stays clear of the page, of its right-side progress indicator and of the corner widgets at every stop; then the corners. Round 1 (w): the corners. */
    var spots = set === "x" ? [["top", "center"], ["bottom", "left"], ["top", "left"], ["bottom", "right"], ["top", "right"]]
      : [["bottom", "right"], ["bottom", "left"], ["top", "right"], ["top", "left"]];
    for (var i = 0; i < spots.length; i++) {
      nav.style.top = nav.style.bottom = nav.style.left = nav.style.right = "auto";
      nav.style.transform = spots[i][1] === "center" ? "translateX(-50%)" : "";
      nav.style[spots[i][0]] = "10px";
      if (spots[i][1] === "center") nav.style.left = "50%"; else nav.style[spots[i][1]] = "10px";
      if (clear()) return;
    }
    nav.style.transform = ""; nav.style.top = nav.style.left = "auto"; nav.style.bottom = nav.style.right = "10px";
  }
  place();
  window.addEventListener("load", place);

  /* capture phase: variants that step sections with the arrow keys must not swallow these */
  window.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var t = e.target;
    if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return;
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    e.stopImmediatePropagation();
    go(e.key === 'ArrowRight' ? 1 : -1);
  }, true);
})();
