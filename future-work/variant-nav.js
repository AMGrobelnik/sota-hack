/* Previous/next switching between the future-work variants f1..f10: a small pill and the left and right arrow keys. Same pattern as how-it-works/variant-nav.js. */
(function () {
  var BUILT = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  var m = location.pathname.match(/\/f(\d+)(?:\.html)?$/);
  var cur = m ? parseInt(m[1], 10) : 0;
  var at = BUILT.indexOf(cur);
  if (at < 0) return;
  function file(d) { return 'f' + BUILT[(at + d + BUILT.length) % BUILT.length] + '.html'; }
  function go(d) { location.href = file(d); }

  var css = document.createElement('style');
  css.textContent =
    '#vnav{position:fixed;right:10px;bottom:10px;z-index:2147483000;display:flex;align-items:center;gap:2px;' +
    'padding:2px 4px;border-radius:999px;background:rgba(20,22,28,.88);color:#fff;border:1px solid rgba(255,255,255,.35);' +
    'font:600 13px/1 system-ui,-apple-system,"Segoe UI",sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.35)}' +
    '#vnav a{color:#fff;text-decoration:none;padding:6px 8px;border-radius:999px;display:inline-block}' +
    '#vnav a:hover{background:rgba(255,255,255,.2)}' +
    '#vnav a:focus-visible{outline:2px solid #fff;outline-offset:1px;box-shadow:0 0 0 4px #1a56db}' +
    '#vnav span{padding:6px 4px}' +
    '#vnav .a{font-size:17px;line-height:1}';
  document.head.appendChild(css);

  var nav = document.createElement('nav');
  nav.id = 'vnav';
  nav.setAttribute('aria-label', 'Switch variant');
  nav.innerHTML =
    '<a class="a" href="' + file(-1) + '" rel="prev" aria-label="Previous variant">‹</a>' +
    '<span>f ' + cur + ' / ' + BUILT.length + '</span>' +
    '<a class="a" href="' + file(1) + '" rel="next" aria-label="Next variant">›</a>';
  document.body.appendChild(nav);

  /* park in the first corner where it covers no text, link, control or picture */
  function clear() {
    var r = nav.getBoundingClientRect();
    var all = document.body.getElementsByTagName('*');
    for (var i = 0; i < all.length; i++) {
      var e = all[i];
      if (nav.contains(e) || /^(SCRIPT|STYLE|PATH|LINE|G|DEFS|MARKER)$/i.test(e.tagName)) continue;
      var leaf = !e.children.length || /^(A|BUTTON|SVG|IMG|CANVAS)$/i.test(e.tagName);
      if (!leaf) continue;
      if (!e.textContent.trim() && !/^(SVG|IMG|CANVAS|INPUT)$/i.test(e.tagName)) continue;
      var cs = getComputedStyle(e);
      if (cs.visibility === 'hidden' || cs.display === 'none' || cs.opacity === '0') continue;
      var q = e.getBoundingClientRect();
      if (/^(SVG|IMG|CANVAS)$/i.test(e.tagName) && q.width * q.height > 0.4 * innerWidth * innerHeight) continue;
      if (q.width && q.height && q.left < r.right && q.right > r.left && q.top < r.bottom && q.bottom > r.top) return false;
    }
    return true;
  }
  function place() {
    var spots = [['bottom', 'right'], ['bottom', 'left'], ['top', 'right'], ['top', 'left']];
    for (var i = 0; i < spots.length; i++) {
      nav.style.top = nav.style.bottom = nav.style.left = nav.style.right = 'auto';
      nav.style[spots[i][0]] = '10px';
      nav.style[spots[i][1]] = '10px';
      if (clear()) return;
    }
    nav.style.top = nav.style.left = 'auto'; nav.style.bottom = nav.style.right = '10px';
  }
  place();
  window.addEventListener('load', place);

  /* on a phone the sections fill the width, so a fixed pill would cover them while scrolling: show it only at the end of the page, by the footer */
  nav.style.transition = 'opacity .2s';
  function peek() {
    var narrow = innerWidth <= 600;
    var se = document.scrollingElement || document.documentElement;
    var show = !narrow || scrollY + innerHeight >= se.scrollHeight - 160;
    nav.style.opacity = show ? '1' : '0';
    nav.style.pointerEvents = show ? 'auto' : 'none';
    nav.style.visibility = show ? 'visible' : 'hidden';
  }
  peek();
  window.addEventListener('scroll', peek, { passive: true });
  window.addEventListener('resize', peek);

  /* capture phase: a variant that steps a control with the arrow keys must not swallow these, unless focus is in a form field or slider */
  window.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var t = e.target;
    if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable || /^(slider|spinbutton|radio|tab)$/.test(t.getAttribute && t.getAttribute('role') || ''))) return;
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    e.stopImmediatePropagation();
    go(e.key === 'ArrowRight' ? 1 : -1);
  }, true);
})();
