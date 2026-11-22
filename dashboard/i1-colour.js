/*
 * i1-colour.js: the colour that carries meaning on the ChipIn i1 dashboard, in one place.
 *   pass       green   (#0b5a3f text, #e6f5ed fill), the pass pills, a target chip met, a key number that clears its target
 *   fail       red     (#9f2a20 text, #fdf0ee fill), the fail pills, a target chip missed, a key number that misses
 *   estimated  amber-brown (#7a4508), italic with a dotted underline; the "estimated" pill is outlined in it
 *   chosen     the brand accent (--blue7), the chosen chip's figures and bars
 * The summary card and the Why this size panel colour themselves (../i1-summary.js, ../i1-whysize.js); this
 * file covers what the page renders: estimated figures, the target chips and the key-number tiles.
 * Every text colour here is at least 4.5 to 1 against its background. The sidebar and the start screen are untouched.
 */
(function () {
  "use strict";
  var CSS = [
    ".est{color:#7a4508;text-decoration-color:rgb(122 69 8/.55)}",
    ".mk.est{color:#7a4508;background:#fff;box-shadow:inset 0 0 0 1px #d6b48c}",
    // target chips in the run header: met in green, missed in red, the plotted one keeps its blue ring
    ".ovh .tgt:has(.pf.ok){background:#f2faf6;border-color:#a8d8bf;color:#0b5a3f}",
    ".ovh .tgt:has(.pf.no){background:#fdf3f1;border-color:#efb9b0;color:#9f2a20}",
    ".ovh .tgt.pri:has(.pf.ok),.ovh .tgt.pri:has(.pf.no){box-shadow:inset 0 0 0 1px currentColor}",
    // key numbers: green when the figure clears its target, red when it misses
    ".ov .tile:has(.ts .pf.ok) .tv{color:#0b5a3f}",
    ".ov .tile:has(.ts .pf.no) .tv{color:#9f2a20}",
    ".ov .tile .tl{color:var(--i700);font-weight:600}",
  ].join("\n");
  var s = document.createElement("style"); s.id = "colour-styles"; s.textContent = CSS; document.head.appendChild(s);
})();
