/* ChipVoice: live voice dictation for text fields.
 *
 * Usage: <textarea data-voice data-voice-anchor="#send"></textarea>
 *        <script src="voice.js"></script>
 *
 * Any textarea or text input with data-voice gets a microphone button, placed
 * just before the element matched by data-voice-anchor (searched inside the
 * field's form, then the page), else right after the field. Speech is
 * transcribed live at the caret. Fields added later are picked up by a
 * MutationObserver; ChipVoice.attach(root) does the same on demand.
 *
 * Recognition sits behind a small provider interface so a server-streaming
 * provider can be added later without touching the UI:
 *   ChipVoice.registerProvider('name', factory)
 *   factory({ lang, field }) -> { start(), stop(),
 *     onInterim(text), onFinal(text), onError({ code }), onState(state) }
 *   The four on* callbacks are assigned by ChipVoice before start().
 *   onError codes: 'denied' | 'no-mic' | 'network' | 'engine'.
 *   onState values: 'listening' | 'speech' | 'idle'.
 *   factory.isSupported() is optional; a false result disables the button.
 *   A field picks a provider with data-voice-provider="name" (default 'browser').
 * stop() must end the session at once and emit nothing afterwards.
 */
(function () {
  'use strict';
  if (window.ChipVoice) return;

  var SILENCE_MS = 60000;
  var UNSUPPORTED = 'Voice input needs Chrome, Edge or Safari';
  var MESSAGES = {
    denied: 'Microphone access is off for this site',
    'no-mic': 'No microphone was found',
    network: 'Voice input lost its connection. Try again.',
    engine: 'Voice input stopped unexpectedly. Try again.'
  };
  var SVG = 'viewBox="0 0 24 24" aria-hidden="true" focusable="false"';
  var ICON_MIC = '<svg ' + SVG + '><rect x="9" y="3" width="6" height="11" rx="3"/>' +
    '<path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/></svg>';
  var ICON_MIC_OFF = '<svg ' + SVG + '><path d="M15 9.5V6a3 3 0 0 0-5.7-1.3M9 9v2a3 3 0 0 0 4.9 2.3"/>' +
    '<path d="M18.5 11a6.5 6.5 0 0 1-.9 3.3M5.5 11a6.5 6.5 0 0 0 10.2 5.3M12 17.5V21M4 4l16 16"/></svg>';
  var ICON_X = '<svg ' + SVG + '><path d="M7 7l10 10M17 7 7 17"/></svg>';

  var CSS = [
    '.cv-mic{position:relative;flex:none;box-sizing:border-box;width:36px;height:36px;margin:0 0 0 auto;padding:0;border:0;border-radius:50%;',
    'display:inline-grid;place-items:center;vertical-align:middle;background:transparent;color:var(--i550,#525266);cursor:pointer;',
    'transition:background-color .12s,color .12s;-webkit-tap-highlight-color:transparent}',
    '.cv-mic svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;pointer-events:none}',
    '.cv-mic:hover{background:rgb(0 0 0/.05);color:var(--i800,#2f2f44)}',
    '.cv-mic:focus-visible{outline:2px solid var(--blue,#3b82f6);outline-offset:2px}',
    '.cv-mic.cv-on,.cv-mic.cv-on:hover{background:rgb(37 99 235/.1);color:var(--blue6,#2563eb)}',
    '.cv-mic.cv-on::after{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;animation:cv-pulse 1.8s ease-out infinite}',
    '.cv-mic.cv-on.cv-speaking::after{animation-duration:.9s}',
    '@keyframes cv-pulse{0%{box-shadow:0 0 0 0 rgb(37 99 235/.34)}70%,100%{box-shadow:0 0 0 7px rgb(37 99 235/0)}}',
    '.cv-mic:disabled,.cv-mic:disabled:hover{cursor:not-allowed;background:transparent;color:var(--i400,#64647a)}',
    '.cv-anchor{margin-left:0!important}',
    '.cv-msg{box-sizing:border-box;width:100%;display:flex;align-items:center;gap:8px;margin:8px auto 0;padding:0 4px 0 20px;',
    'font:12.5px/1.4 var(--sans,-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif);color:var(--i700,#3c3c50)}',
    '.cv-msg::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--bad,#ef4444);flex:none}',
    '.cv-msg-x{flex:none;width:22px;height:22px;margin:0;padding:0;border:0;border-radius:6px;display:grid;place-items:center;',
    'background:transparent;color:var(--i550,#525266);cursor:pointer}',
    '.cv-msg-x:hover{background:rgb(0 0 0/.05)}',
    '.cv-msg-x:focus-visible{outline:2px solid var(--blue,#3b82f6);outline-offset:1px}',
    '.cv-msg-x svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round}',
    '.cv-sr{position:absolute!important;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}',
    '@media (prefers-reduced-motion:reduce){.cv-mic,.cv-msg-x{transition:none}',
    '.cv-mic.cv-on::after{animation:none;box-shadow:0 0 0 3px rgb(37 99 235/.2)}',
    '.cv-mic.cv-on.cv-speaking::after{box-shadow:0 0 0 4px rgb(37 99 235/.34)}}'
  ].join('\n');

  /* ---------- providers ---------- */

  var providers = Object.create(null);

  function browserCtor() { return window.SpeechRecognition || window.webkitSpeechRecognition || null; }

  function browserProvider(opts) {
    var Ctor = browserCtor();
    var rec = null, want = false, startedAt = 0, quickEnds = 0;
    var p = { onInterim: noop, onFinal: noop, onError: noop, onState: noop, start: start, stop: stop };
    var codes = { 'not-allowed': 'denied', 'service-not-allowed': 'denied', 'audio-capture': 'no-mic', network: 'network' };

    function fail(code) { want = false; detach(rec); rec = null; p.onError({ code: code }); }
    function make() {
      var r = new Ctor();
      r.lang = opts.lang; r.continuous = true; r.interimResults = true; r.maxAlternatives = 1;
      r.onstart = function () { startedAt = Date.now(); p.onState('listening'); };
      r.onspeechstart = function () { p.onState('speech'); };
      r.onspeechend = function () { p.onState('listening'); };
      r.onresult = function (e) {
        var interim = '';
        for (var i = e.resultIndex; i < e.results.length; i++) {
          var res = e.results[i], t = res[0] ? res[0].transcript : '';
          if (res.isFinal) p.onFinal(t); else interim += t;
        }
        p.onInterim(interim);
        quickEnds = 0;
      };
      r.onerror = function (e) {
        // no-speech is the engine's own short silence timeout: keep listening.
        if (e.error === 'no-speech' || e.error === 'aborted') return;
        fail(codes[e.error] || 'engine');
      };
      r.onend = function () {
        if (!want || rec !== r) return;
        // The engine ends on its own after pauses; restart while the user wants it.
        if (Date.now() - startedAt < 1000 && ++quickEnds > 4) return fail('engine');
        try { r.start(); } catch (err) { fail('engine'); }
      };
      return r;
    }
    function detach(r) {
      if (r) r.onstart = r.onspeechstart = r.onspeechend = r.onresult = r.onerror = r.onend = null;
    }
    function start() {
      want = true; quickEnds = 0; rec = make();
      try { rec.start(); } catch (err) { fail('engine'); }
    }
    function stop() {
      var r = rec;
      want = false; rec = null; detach(r);
      if (r) { try { r.abort(); } catch (err) { /* already ended */ } }
      p.onState('idle');
    }
    return p;
  }
  browserProvider.isSupported = function () { return !!browserCtor(); };
  providers.browser = browserProvider;

  function providerFor(field) {
    return providers[field.getAttribute('data-voice-provider') || 'browser'] || providers.browser;
  }
  function supported(factory) {
    try { return typeof factory.isSupported !== 'function' || !!factory.isSupported(); } catch (err) { return false; }
  }

  /* ---------- text composition ---------- */

  function cap(s) { return s.replace(/^(\W*)(\p{Ll})/u, function (m, a, b) { return a + b.toUpperCase(); }); }
  function sentenceStart(before) { return /^\s*$/.test(before) || /[.!?]["'”’)\]]*\s*$/.test(before) || /\n\s*$/.test(before); }

  function joinSpoken(parts) {
    var out = '';
    parts.forEach(function (raw) {
      var s = raw.replace(/\s+/g, ' ').trim();
      if (!s) return;
      if (out && sentenceStart(out)) s = cap(s);
      out += (out ? ' ' : '') + s;
    });
    return out;
  }

  function compose(prefix, spoken, suffix) {
    if (!spoken) return { text: prefix + suffix, caret: prefix.length };
    if (sentenceStart(prefix)) spoken = cap(spoken);
    var lead = prefix && !/\s$/.test(prefix) ? ' ' : '';
    var trail = suffix && !/^[\s.,!?;:)\]]/.test(suffix) ? ' ' : '';
    var head = prefix + lead + spoken;
    return { text: head + trail + suffix, caret: head.length };
  }

  /* ---------- shared page state ---------- */

  var active = null;
  var controllers = new Set();
  var live = null;

  function announce(text) {
    if (!live) {
      live = document.createElement('span');
      live.className = 'cv-sr'; live.setAttribute('aria-live', 'polite');
      document.body.appendChild(live);
    }
    live.textContent = text;
  }
  function noop() {}

  /* ---------- one field ---------- */

  function Controller(field) {
    this.field = field;
    this.form = field.form || null;
    this.listening = false;
    this.msg = null;
    var btn = this.btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'cv-mic';
    btn.setAttribute('aria-pressed', 'false');
    var self = this;
    btn.addEventListener('click', function () { self.listening ? self.stop() : self.start(); });
    btn.addEventListener('keydown', function (e) { self.escape(e); });
    field.addEventListener('keydown', function (e) { self.escape(e); });
    field.addEventListener('input', function (e) { if (self.listening && e.isTrusted) self.rebase(); });
    field.addEventListener('mouseup', function () { if (self.listening) self.rebase(); });
    this.place();
    this.refresh();
  }

  Controller.prototype.place = function () {
    var f = this.field, sel = f.getAttribute('data-voice-anchor'), anchor = null;
    if (sel) {
      try { anchor = (this.form || f.parentElement).querySelector(sel) || document.querySelector(sel); } catch (err) { anchor = null; }
    }
    this.anchor = anchor;
    if (anchor) {
      anchor.parentNode.insertBefore(this.btn, anchor);
      var d = getComputedStyle(anchor.parentNode).display;
      if (d === 'flex' || d === 'inline-flex') anchor.classList.add('cv-anchor');
      var self = this;
      anchor.addEventListener('click', function () { if (self.listening) self.stop(); });
    } else {
      f.insertAdjacentElement('afterend', this.btn);
    }
  };

  Controller.prototype.refresh = function () {
    var ok = supported(providerFor(this.field));
    var b = this.btn;
    b.disabled = !ok || this.field.disabled;
    if (!ok) {
      if (this.listening) this.stop();
      b.innerHTML = ICON_MIC_OFF;
      b.setAttribute('aria-label', 'Voice input unavailable');
      b.title = UNSUPPORTED;
    } else {
      b.innerHTML = ICON_MIC;
      this.label();
    }
  };

  Controller.prototype.label = function () {
    var t = this.listening ? 'Stop voice input' : 'Start voice input';
    this.btn.setAttribute('aria-label', t);
    this.btn.title = t;
  };

  Controller.prototype.escape = function (e) {
    if (e.key === 'Escape' && this.listening) { e.preventDefault(); e.stopPropagation(); this.stop(); }
  };

  Controller.prototype.rebase = function () {
    var f = this.field, v = f.value;
    this.prefix = v.slice(0, f.selectionStart == null ? v.length : f.selectionStart);
    this.suffix = v.slice(f.selectionEnd == null ? v.length : f.selectionEnd);
    this.finals = []; this.interim = '';
  };

  Controller.prototype.render = function () {
    var out = compose(this.prefix, joinSpoken(this.finals.concat([this.interim])), this.suffix);
    var f = this.field;
    if (f.value === out.text) return;
    f.value = out.text;
    try { f.setSelectionRange(out.caret, out.caret); } catch (err) { /* type without selection */ }
    var ev;
    try { ev = new InputEvent('input', { bubbles: true, inputType: 'insertText', data: null }); } catch (err) { ev = new Event('input', { bubbles: true }); }
    f.dispatchEvent(ev);
    // keep the caret in view while the field grows or scrolls
    if (f.scrollHeight > f.clientHeight && out.caret === f.value.length) f.scrollTop = f.scrollHeight;
  };

  Controller.prototype.heard = function () {
    var self = this;
    this.armSilence();
    this.btn.classList.add('cv-speaking');
    clearTimeout(this.speakT);
    this.speakT = setTimeout(function () { self.btn.classList.remove('cv-speaking'); }, 900);
  };

  Controller.prototype.armSilence = function () {
    var self = this;
    clearTimeout(this.silenceT);
    this.silenceT = setTimeout(function () { if (self.listening) self.stop(); }, SILENCE_MS);
  };

  Controller.prototype.start = function () {
    if (this.listening || this.btn.disabled || this.field.disabled || this.field.readOnly) return;
    if (active && active !== this) active.stop();
    active = this;
    this.clearMsg();
    this.rebase();
    this.listening = true;
    this.placeholder = this.field.getAttribute('placeholder');
    if (!this.field.value) this.field.setAttribute('placeholder', 'Listening…');
    this.btn.classList.add('cv-on');
    this.btn.setAttribute('aria-pressed', 'true');
    this.label();
    announce('Listening');
    this.armSilence();

    var self = this;
    var lang = (this.field.closest('[lang]') || document.documentElement).getAttribute('lang') || 'en-GB';
    var p = this.provider = providerFor(this.field)({ lang: lang, field: this.field });
    p.onInterim = function (t) { if (self.provider !== p) return; self.interim = t || ''; if (t) self.heard(); self.render(); };
    p.onFinal = function (t) { if (self.provider !== p) return; self.interim = ''; if (t) { self.finals.push(t); self.heard(); } self.render(); };
    p.onState = function (s) { if (self.provider !== p) return; if (s === 'speech') self.heard(); };
    p.onError = function (err) {
      if (self.provider !== p) return;
      self.stop();
      self.showMsg(MESSAGES[(err && err.code) || 'engine'] || MESSAGES.engine);
    };
    try { p.start(); } catch (err) { p.onError({ code: 'engine' }); }
  };

  Controller.prototype.stop = function () {
    if (!this.listening) return;
    var p = this.provider;
    this.provider = null;
    this.listening = false;
    if (active === this) active = null;
    clearTimeout(this.silenceT); clearTimeout(this.speakT);
    if (p) { try { p.stop(); } catch (err) { /* provider already stopped */ } }
    // whatever was on screen stays as typed text
    this.finals = []; this.interim = '';
    if (this.placeholder == null) this.field.removeAttribute('placeholder');
    else this.field.setAttribute('placeholder', this.placeholder);
    this.btn.classList.remove('cv-on', 'cv-speaking');
    this.btn.setAttribute('aria-pressed', 'false');
    this.label();
    announce('Stopped listening');
  };

  Controller.prototype.showMsg = function (text) {
    this.clearMsg();
    var box = this.form || this.field.parentElement;
    var m = this.msg = document.createElement('div');
    m.className = 'cv-msg';
    m.setAttribute('role', 'status');
    var span = document.createElement('span');
    span.textContent = text;
    var x = document.createElement('button');
    x.type = 'button'; x.className = 'cv-msg-x';
    x.setAttribute('aria-label', 'Dismiss'); x.title = 'Dismiss';
    x.innerHTML = ICON_X;
    var self = this;
    x.addEventListener('click', function () { self.clearMsg(); self.btn.focus(); });
    m.appendChild(span); m.appendChild(x);
    var mw = getComputedStyle(box).maxWidth;
    if (mw && mw !== 'none') m.style.maxWidth = mw;
    box.insertAdjacentElement('afterend', m);
  };

  Controller.prototype.clearMsg = function () {
    if (this.msg) { this.msg.remove(); this.msg = null; }
  };

  /* ---------- wiring ---------- */

  var bound = new WeakMap();

  function isField(el) {
    if (!el || el.nodeType !== 1 || !el.hasAttribute('data-voice')) return false;
    if (el.tagName === 'TEXTAREA') return true;
    return el.tagName === 'INPUT' && /^(text|search|)$/i.test(el.getAttribute('type') || '');
  }

  function attach(root) {
    root = root || document;
    var list = [];
    if (root.nodeType === 1 && isField(root)) list.push(root);
    if (root.querySelectorAll) list.push.apply(list, root.querySelectorAll('[data-voice]'));
    list.forEach(function (f) {
      if (!isField(f) || bound.has(f)) return;
      var c = new Controller(f);
      bound.set(f, c);
      controllers.add(c);
    });
  }

  function prune() {
    controllers.forEach(function (c) {
      if (c.field.isConnected) return;
      c.stop(); c.clearMsg(); controllers.delete(c);
    });
  }

  function registerProvider(name, factory) {
    if (typeof name !== 'string' || !name || typeof factory !== 'function') throw new TypeError('registerProvider(name, factory)');
    providers[name] = factory;
    controllers.forEach(function (c) { if (!c.listening) c.refresh(); });
  }

  function init() {
    if (!document.getElementById('cv-style')) {
      var st = document.createElement('style');
      st.id = 'cv-style';
      st.textContent = CSS;
      document.head.appendChild(st);
    }
    attach(document);
    new MutationObserver(function (records) {
      var gone = false;
      records.forEach(function (r) {
        if (r.type === 'attributes') { attach(r.target); return; }
        r.addedNodes.forEach(function (n) { if (n.nodeType === 1) attach(n); });
        if (r.removedNodes.length) gone = true;
      });
      if (gone) prune();
    }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-voice'] });

    // stop before the page's own submit handler reads the field
    document.addEventListener('submit', function (e) {
      if (active && active.form && active.form === e.target) active.stop();
    }, true);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && active) active.stop();
    });
  }

  window.ChipVoice = Object.freeze({ registerProvider: registerProvider, attach: attach });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
