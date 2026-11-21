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
 * Two engines ship here:
 *   'browser'  the browser's own SpeechRecognition, word by word.
 *   'server'   records the microphone, cuts the speech into phrases at pauses
 *              and sends each phrase to POST <base>/api/transcribe; the text
 *              is inserted in spoken order as each answer arrives.
 * The server engine is chosen when an endpoint is known and its /api/health
 * says transcription is available: first a connected window.ChipInLive (the
 * local backend), else window.CHIPIN_VOICE.endpoint from voice-config.js,
 * which this script loads from its own folder. Otherwise the browser engine
 * listens. A field can force one with data-voice-provider="name".
 *
 * Provider interface:
 *   ChipVoice.registerProvider('name', factory)
 *   factory({ lang, field, context }) -> { start(), stop(), finish()?,
 *     onInterim(text), onFinal(text), onError({ code }), onState(state), onNotice(text) }
 *   The on* callbacks are assigned by ChipVoice before start().
 *   context() returns up to 200 characters of the text dictated so far.
 *   onError codes: 'denied' | 'no-mic' | 'network' | 'engine' | 'switch'
 *     ('switch': the provider gave up for this page; another engine takes over).
 *   onState values: 'listening' | 'speech' | 'idle' | 'transcribing' | 'transcribed'.
 *   factory.isSupported() is optional; a false result disables the button.
 * stop() must end the session at once and emit nothing afterwards.
 * finish(), if present, ends the capture but keeps delivering text for what
 * was already heard; its promise resolves once everything is delivered.
 */
(function () {
  'use strict';
  if (window.ChipVoice) return;

  var SELF_SRC = (document.currentScript && document.currentScript.src) || '';
  var SILENCE_MS = 60000;
  var UNSUPPORTED = 'Voice input needs Chrome, Edge or Safari';
  var MESSAGES = {
    denied: 'Microphone access is off for this site',
    'no-mic': 'No microphone was found',
    network: 'Voice input lost its connection. Try again.',
    engine: 'Voice input stopped unexpectedly. Try again.',
    lost: 'A phrase could not be transcribed. Please repeat it or type it.',
    switched: 'Server transcription is not working, so the browser’s own speech recognition is listening now.',
    serverDown: 'Server transcription is not working. Try again later or type instead.'
  };
  var ENGINE_NAMES = { server: 'server transcription', browser: 'the browser’s speech recognition' };
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
    '.cv-mic.cv-busy::before{content:"";position:absolute;top:4px;right:4px;width:7px;height:7px;border-radius:50%;pointer-events:none;',
    'background:var(--blue6,#2563eb);animation:cv-blink 1s ease-in-out infinite}',
    '@keyframes cv-blink{0%,100%{opacity:.25}50%{opacity:1}}',
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
    '.cv-mic.cv-on.cv-speaking::after{box-shadow:0 0 0 4px rgb(37 99 235/.34)}',
    '.cv-mic.cv-busy::before{animation:none;opacity:.8}}'
  ].join('\n');

  function noop() {}

  /* ---------- browser engine ---------- */

  var providers = Object.create(null);

  function browserCtor() { return window.SpeechRecognition || window.webkitSpeechRecognition || null; }

  function browserProvider(opts) {
    var Ctor = browserCtor();
    var rec = null, want = false, startedAt = 0, quickEnds = 0;
    var p = { onInterim: noop, onFinal: noop, onError: noop, onState: noop, onNotice: noop, start: start, stop: stop };
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

  /* ---------- server endpoint discovery ---------- */

  var HEALTH_TTL_MS = 30000;
  var engine = { target: null, key: '', checkedAt: 0, pending: null, pendingKey: '', off: false };

  function cleanBase(u) {
    return String(u).trim().replace(/\/+$/, '').replace(/\/api\/transcribe$/, '').replace(/\/api$/, '');
  }
  function liveToken(L) {
    // Read what the ChipInLive adapter already holds; never stored anywhere new.
    try { if (typeof L.token === 'string' && L.token) return L.token; } catch (err) { /* no getter */ }
    try { return window.sessionStorage.getItem('chipin.token:' + L.base); } catch (err) { return null; }
  }
  function candidate() {
    var L = window.ChipInLive;
    if (L && L.status === 'connected' && L.base && liveToken(L)) return { base: cleanBase(L.base), source: 'local' };
    var cfg = window.CHIPIN_VOICE;
    if (cfg && typeof cfg.endpoint === 'string' && cfg.endpoint.trim()) return { base: cleanBase(cfg.endpoint), source: 'public' };
    return null;
  }
  function candidateKey(c) { return c ? c.source + ' ' + c.base : ''; }
  function transcribeReady(h) {
    if (!h || typeof h !== 'object') return false;
    var t = h.transcribe !== undefined ? h.transcribe : h.transcription;
    if (t === true) return true;
    if (t && typeof t === 'object') return t.available === true || t.ready === true || t.ok === true || t.enabled === true;
    if (Array.isArray(h.features) && h.features.indexOf('transcribe') >= 0) return true;
    return !!(h.capabilities && h.capabilities.transcribe === true);
  }
  function tokenFor(target) {
    if (target.source !== 'local') return null;
    var L = window.ChipInLive;
    return L && cleanBase(L.base || '') === target.base ? liveToken(L) : null;
  }
  function timedFetch(url, init, ms) {
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    if (ctl) init.signal = ctl.signal;
    var t = setTimeout(function () { if (ctl) ctl.abort(); }, ms);
    return fetch(url, init).then(function (r) { clearTimeout(t); return r; }, function (e) { clearTimeout(t); throw e; });
  }
  function serverTarget() { return engine.off ? null : engine.target; }

  function checkEngine(force) {
    var c = candidate(), key = candidateKey(c);
    if (engine.pending && engine.pendingKey === key) return engine.pending;
    if (!force && key === engine.key && Date.now() - engine.checkedAt < HEALTH_TTL_MS) return Promise.resolve(engine.target);
    if (!c) {
      engine.pending = null; engine.key = ''; engine.target = null; engine.checkedAt = Date.now();
      refreshAll();
      return Promise.resolve(null);
    }
    engine.pendingKey = key;
    var pr = engine.pending = timedFetch(c.base + '/api/health', { cache: 'no-store' }, 5000)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (h) { return transcribeReady(h) ? c : null; }, function () { return null; })
      .then(function (t) {
        if (engine.pending !== pr) return t;
        engine.pending = null; engine.key = key; engine.target = t; engine.checkedAt = Date.now();
        refreshAll();
        return t;
      });
    return pr;
  }

  function switchServerOff() {
    engine.off = true;
    refreshAll();
  }

  /* ---------- server engine ---------- */

  var TICK_MS = 30;
  var CALIBRATE_MS = 400;
  var ONSET_MS = 90;          // this long above the speech threshold starts speech
  var WORD_GAP_MS = 300;      // this long below it ends a burst of speech
  var PAUSE_MS = 700;         // a pause this long after speech closes the phrase
  var MIN_VOICED_MS = 160;    // a phrase with less speech than this is never sent
  var SOFT_CUT_MS = 20000;    // past this, any 150 ms gap between words closes the phrase
  var HARD_CUT_MS = 26000;    // past this, the phrase is closed regardless
  var RECYCLE_MS = 3000;      // a speech-free recording this old is thrown away and restarted
  var REQUEST_MS = 20000;
  var FLUSH_MAX_MS = 12000;
  var MAX_BYTES = 2000000;
  var MAX_FAILED_PHRASES = 2;
  var TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4;codecs=mp4a.40.2', 'audio/mp4'];

  function pickMime() {
    if (!window.MediaRecorder || typeof MediaRecorder.isTypeSupported !== 'function') return '';
    for (var i = 0; i < TYPES.length; i++) {
      try { if (MediaRecorder.isTypeSupported(TYPES[i])) return TYPES[i]; } catch (err) { /* next */ }
    }
    return '';
  }
  function contentType(m) {
    var base = String(m || '').split(';')[0].trim().toLowerCase();
    if (/^audio\/(webm|ogg|mp4|wav)$/.test(base)) return base;
    if (/webm/.test(base)) return 'audio/webm';
    if (/ogg/.test(base)) return 'audio/ogg';
    if (/mp4|m4a|aac/.test(base)) return 'audio/mp4';
    return base || 'audio/webm';
  }
  // Running the browser recogniser next to the recording is reliable on
  // desktop Chromium only; elsewhere it can steal or break the microphone.
  function previewSafe() {
    var cfg = window.CHIPIN_VOICE;
    if (cfg && cfg.preview === false) return false;
    var ua = navigator.userAgent || '';
    return !!browserCtor() && navigator.vendor === 'Google Inc.' && /Chrome\//.test(ua) &&
      !/Android|Mobile|iPhone|iPad|iPod|CriOS|EdgiOS/i.test(ua);
  }
  function squash(s) { return String(s || '').replace(/\s+/g, ' ').trim(); }

  function serverProvider(opts) {
    var p = { onInterim: noop, onFinal: noop, onError: noop, onState: noop, onNotice: noop, start: start, stop: stop, finish: finish };
    var target = serverTarget();
    var lang = String(opts.lang || 'en').split('-')[0].toLowerCase() || 'en';
    var stream = null, ctx = null, analyser = null, buf = null, tick = null, mime = '';
    var seg = null, queue = [], seq = 0, failed = 0, ended = false, live = false, busy = false;
    var startedAt = 0, calib = [], floorDb = -70, above = 0, quiet = 0, speaking = false, lastVoiceAt = 0;
    var finishing = null, finishDone = noop, flushT = null;
    var pv = null;

    function fail(code) { if (ended) return; teardown(); p.onError({ code: code }); }

    function start() {
      if (!target) return fail('engine');
      live = true;
      startedAt = Date.now();
      // Create the audio context inside the click so Safari lets it run.
      var AC = window.AudioContext || window.webkitAudioContext;
      try { ctx = new AC(); } catch (err) { return fail('engine'); }
      if (ctx.state === 'suspended' && ctx.resume) ctx.resume().catch(noop);
      navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 }
      }).then(function (s) {
        if (ended) { s.getTracks().forEach(function (t) { t.stop(); }); return; }
        stream = s;
        var src = ctx.createMediaStreamSource(s);
        analyser = ctx.createAnalyser();
        analyser.fftSize = 1024;
        buf = new Float32Array(analyser.fftSize);
        // A silent sink keeps the graph pulling audio in every browser; it plays nothing.
        var mute = ctx.createGain();
        mute.gain.value = 0;
        src.connect(analyser); analyser.connect(mute); mute.connect(ctx.destination);
        mime = pickMime();
        startedAt = Date.now();
        newSegment();
        tick = setInterval(onTick, TICK_MS);
        p.onState('listening');
        startPreview();
      }, function (err) {
        var n = err && err.name;
        fail(n === 'NotAllowedError' || n === 'SecurityError' ? 'denied' :
          n === 'NotFoundError' || n === 'OverconstrainedError' || n === 'NotReadableError' ? 'no-mic' : 'engine');
      });
    }

    /* recording: one MediaRecorder per phrase, so each phrase is a whole file */

    function newSegment() {
      var rec;
      try { rec = mime ? new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: 48000 }) : new MediaRecorder(stream); } catch (err) {
        try { rec = new MediaRecorder(stream); } catch (err2) { return fail('engine'); }
      }
      var s = { rec: rec, chunks: [], at: Date.now(), voiced: 0 };
      rec.ondataavailable = function (e) { if (e.data && e.data.size) s.chunks.push(e.data); };
      try { rec.start(); } catch (err) { return fail('engine'); }
      seg = s;
    }

    function closeSegment(keep) {
      var s = seg, ph = null;
      seg = null;
      if (!s) return;
      if (keep) {
        ph = { id: ++seq, state: 'recording', text: '', preview: null };
        queue.push(ph);
        notePreviewOwner(ph);
        setBusy();
      }
      s.rec.onstop = function () {
        if (!ph || ended) return;
        send(ph, new Blob(s.chunks, { type: s.rec.mimeType || mime || 'audio/webm' }));
      };
      try { s.rec.stop(); } catch (err) { if (ph) phraseFailed(ph, false); }
    }

    function cut(keep) {
      closeSegment(keep);
      if (live) newSegment();
    }

    function onTick() {
      if (!analyser || !seg || ended) return;
      analyser.getFloatTimeDomainData(buf);
      var sum = 0;
      for (var i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      var rms = Math.sqrt(sum / buf.length);
      var db = rms > 1e-6 ? 20 * Math.log10(rms) : -120;
      var now = Date.now();

      if (calib) {
        if (now - startedAt < CALIBRATE_MS) { calib.push(db); return; }
        // The quiet end of the first moments is the room's noise floor; if
        // that is loud, someone is already talking, so assume a quiet room.
        calib.sort(function (a, b) { return a - b; });
        var low = calib.length ? calib[Math.floor(calib.length * 0.2)] : -70;
        floorDb = low > -35 ? -65 : Math.max(-90, low);
        calib = null;
      }
      var on = Math.max(floorDb + 12, -50), off = Math.max(floorDb + 6, -56);

      above = db >= on ? above + TICK_MS : 0;
      if (speaking) {
        if (db < off) {
          quiet += TICK_MS;
          if (quiet >= WORD_GAP_MS) { speaking = false; p.onState('listening'); }
        } else { quiet = 0; seg.voiced += TICK_MS; lastVoiceAt = now; }
      } else if (above >= ONSET_MS) {
        speaking = true; quiet = 0; seg.voiced += above; lastVoiceAt = now;
        p.onState('speech');
      }
      // Follow the noise floor: down at once, up slowly (slower still in speech).
      floorDb += (db - floorDb) * (db < floorDb ? 0.3 : speaking ? 0.002 : 0.01);
      floorDb = Math.min(-20, Math.max(-90, floorDb));

      var age = now - seg.at, since = now - lastVoiceAt;
      if (seg.voiced >= MIN_VOICED_MS) {
        if (since >= PAUSE_MS || (age >= SOFT_CUT_MS && since >= 150) || age >= HARD_CUT_MS) cut(true);
      } else if (!speaking && above === 0 && age >= RECYCLE_MS && since >= PAUSE_MS) {
        cut(false); // nothing but silence or a click: never sent
      }
    }

    /* sending: in parallel, inserted strictly in order */

    function send(ph, blob) {
      if (!blob.size) { ph.state = 'done'; return pump(); }
      if (blob.size > MAX_BYTES) return phraseFailed(ph, false);
      ph.state = 'sending';
      attempt(ph, blob, 0);
    }

    function attempt(ph, blob, n) {
      if (ended || ph.state !== 'sending') return;
      var headers = { 'Content-Type': contentType(blob.type) };
      var tok = tokenFor(target);
      if (tok) headers['X-ChipIn-Token'] = tok;
      var hint = contextFor(ph);
      if (hint) headers['X-ChipIn-Context'] = encodeURIComponent(hint);
      timedFetch(target.base + '/api/transcribe?lang=' + encodeURIComponent(lang),
        { method: 'POST', headers: headers, body: blob, cache: 'no-store' }, REQUEST_MS)
        .then(function (r) {
          return r.json().then(function (j) { return { status: r.status, ok: r.ok, body: j }; },
            function () { return { status: r.status, ok: false, body: null }; });
        }, function () { return { status: 0, ok: false, body: null }; })
        .then(function (res) {
          if (ended || ph.state !== 'sending') return;
          if (res.ok && res.body && typeof res.body.text === 'string') {
            ph.text = squash(res.body.text); ph.state = 'done'; failed = 0;
            return pump();
          }
          // No point retrying a refused token, a missing key or a spent cap.
          var fatal = res.status === 401 || res.status === 403 || res.status === 429 || res.status === 503;
          var retry = !fatal && n === 0 && res.status !== 400 && res.status !== 413;
          if (retry) { setTimeout(function () { attempt(ph, blob, 1); }, 400); return; }
          phraseFailed(ph, fatal);
        });
    }

    function contextFor(ph) {
      var before = '';
      try { before = opts.context ? opts.context() : ''; } catch (err) { before = ''; }
      queue.forEach(function (q) { if (q.id < ph.id) before += ' ' + (q.state === 'done' ? q.text : q.preview || ''); });
      return squash(before).slice(-200);
    }

    function phraseFailed(ph, fatal) {
      if (ended || ph.state === 'done') return;
      failed++;
      takePreview(ph);
      ph.text = ph.preview || '';
      ph.state = 'done';
      if (!ph.text) p.onNotice(MESSAGES.lost);
      pump();
      if (fatal || failed >= MAX_FAILED_PHRASES) giveUp();
    }

    function giveUp() {
      if (ended) return;
      switchServerOff();
      queue.forEach(function (q) { if (q.state !== 'done') { takePreview(q); q.text = q.preview || ''; q.state = 'done'; } });
      pump();
      if (finishing) return; // the flush resolves through pump
      teardown();
      p.onError({ code: 'switch' });
    }

    function pump() {
      if (ended) return;
      while (queue.length && queue[0].state === 'done') {
        var ph = queue.shift();
        if (ph.text) p.onFinal(ph.text);
      }
      p.onInterim(previewText());
      setBusy();
      if (finishing && !queue.length) {
        teardown();
        p.onInterim('');
        p.onState('idle');
        finishDone();
      }
    }

    function setBusy() {
      var b = queue.length > 0;
      if (b === busy || ended) return;
      busy = b;
      p.onState(b ? 'transcribing' : 'transcribed');
    }

    /* preview: the browser recogniser's words, shown until the server's replace them */

    function startPreview() {
      if (!previewSafe()) return;
      pv = { rec: null, done: '', interim: '', taken: '', owners: [], startedAt: 0, quick: 0 };
      var Ctor = browserCtor();
      function make() {
        var r = new Ctor();
        r.lang = opts.lang; r.continuous = true; r.interimResults = true; r.maxAlternatives = 1;
        r.onstart = function () { if (pv) pv.startedAt = Date.now(); };
        r.onresult = function (e) {
          if (!pv || pv.rec !== r) return;
          var interim = '', fin = false;
          for (var i = e.resultIndex; i < e.results.length; i++) {
            var res = e.results[i], t = res[0] ? res[0].transcript : '';
            if (res.isFinal) { pv.done = squash(pv.done + ' ' + dropTaken(t)); fin = true; } else interim += t;
          }
          pv.interim = squash(interim);
          pv.quick = 0;
          if (fin && pv.owners.length) givePreview(false);
          p.onInterim(previewText());
        };
        r.onerror = function (e) {
          if (e.error === 'no-speech' || e.error === 'aborted') return;
          stopPreview(); // the recording carries on; only the preview goes
        };
        r.onend = function () {
          if (!pv || pv.rec !== r || !live) return;
          if (Date.now() - pv.startedAt < 1000 && ++pv.quick > 4) return stopPreview();
          try { r.start(); } catch (err) { stopPreview(); }
        };
        return r;
      }
      pv.rec = make();
      try { pv.rec.start(); } catch (err) { stopPreview(); }
    }

    function dropTaken(t) {
      // Words already handed to a phrase as interim text are not counted twice.
      var s = squash(t);
      if (pv.taken && s.toLowerCase().indexOf(pv.taken.toLowerCase()) === 0) s = squash(s.slice(pv.taken.length));
      pv.taken = '';
      return s;
    }

    function notePreviewOwner(ph) {
      if (!pv) return;
      pv.owners.push(ph);
      if (pv.done && !pv.interim) return givePreview(false);
      ph.previewT = setTimeout(function () { if (pv && pv.owners[0] === ph) { givePreview(true); p.onInterim(previewText()); } }, 1500);
    }

    function givePreview(withInterim) {
      var ph = pv && pv.owners.shift();
      if (!ph) return;
      clearTimeout(ph.previewT);
      var text = pv.done;
      if (withInterim && pv.interim) { text += ' ' + pv.interim; pv.taken = pv.interim; pv.interim = ''; }
      ph.preview = squash(text);
      pv.done = '';
    }

    function takePreview(ph) {
      if (ph.preview != null || !pv) return;
      while (pv.owners.length && ph.preview == null) givePreview(true);
    }

    function previewText() {
      var parts = [];
      queue.forEach(function (q) { if (q.state !== 'done' && q.preview) parts.push(q.preview); });
      if (pv) { if (pv.done) parts.push(pv.done); if (pv.interim) parts.push(pv.interim); }
      return squash(parts.join(' '));
    }

    function stopPreview() {
      var x = pv;
      pv = null;
      if (!x) return;
      x.owners.forEach(function (ph) { clearTimeout(ph.previewT); });
      if (x.rec) {
        x.rec.onstart = x.rec.onresult = x.rec.onerror = x.rec.onend = null;
        try { x.rec.abort(); } catch (err) { /* already ended */ }
      }
    }

    /* ending */

    function stopCapture() {
      live = false;
      clearInterval(tick); tick = null;
      if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
      if (ctx && ctx.state !== 'closed') { try { ctx.close().catch(noop); } catch (err) { /* closed */ } }
      analyser = null;
    }

    function teardown() {
      if (ended) return;
      ended = true;
      clearTimeout(flushT);
      if (seg) { var s = seg; seg = null; s.rec.onstop = null; try { s.rec.stop(); } catch (err) { /* stopped */ } }
      stopPreview();
      stopCapture();
    }

    function finish() {
      if (finishing) return finishing;
      finishing = new Promise(function (res) { finishDone = res; });
      if (ended) { finishDone(); return finishing; }
      if (seg) closeSegment(seg.voiced >= MIN_VOICED_MS);
      if (pv) {
        while (pv.owners.length) givePreview(true);
        stopPreview();
      }
      stopCapture();
      flushT = setTimeout(function () {
        // The server is too slow: what the preview heard stands in.
        queue.forEach(function (q) {
          if (q.state === 'done') return;
          q.text = q.preview || ''; q.state = 'done';
          if (!q.text) p.onNotice(MESSAGES.lost);
        });
        pump();
      }, FLUSH_MAX_MS);
      pump();
      return finishing;
    }

    function stop() {
      teardown();
      finishDone();
    }

    return p;
  }
  serverProvider.isSupported = function () {
    var md = navigator.mediaDevices;
    return !!(serverTarget() && md && md.getUserMedia && window.MediaRecorder && (window.AudioContext || window.webkitAudioContext));
  };
  providers.server = serverProvider;

  function engineFor(field) {
    var want = field.getAttribute('data-voice-provider');
    if (want && providers[want]) return want;
    if (supported(providers.server)) return 'server';
    return 'browser';
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
  function refreshAll() {
    controllers.forEach(function (c) { if (!c.listening && !c.finishing) c.refresh(); });
  }

  /* ---------- one field ---------- */

  function Controller(field) {
    this.field = field;
    this.form = field.form || null;
    this.listening = false;
    this.finishing = null;
    this.resend = null;
    this.msg = null;
    var btn = this.btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'cv-mic';
    btn.setAttribute('aria-pressed', 'false');
    var self = this;
    btn.addEventListener('click', function () { self.listening ? self.stop() : self.start(); });
    btn.addEventListener('keydown', function (e) { self.escape(e); });
    btn.addEventListener('pointerenter', function () { checkEngine(false); });
    btn.addEventListener('focus', function () { checkEngine(false); });
    field.addEventListener('keydown', function (e) { self.escape(e); });
    field.addEventListener('input', function (e) { if ((self.listening || self.finishing) && e.isTrusted) self.rebase(); });
    field.addEventListener('mouseup', function () { if (self.listening || self.finishing) self.rebase(); });
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
    } else {
      f.insertAdjacentElement('afterend', this.btn);
    }
  };

  Controller.prototype.refresh = function () {
    var ok = supported(providers[engineFor(this.field)] || providers.browser);
    var b = this.btn;
    b.disabled = !ok || this.field.disabled;
    if (!ok) {
      if (this.listening) this.end();
      b.innerHTML = ICON_MIC_OFF;
      b.setAttribute('aria-label', 'Voice input unavailable');
      b.title = UNSUPPORTED;
    } else {
      b.innerHTML = ICON_MIC;
      this.label();
    }
  };

  Controller.prototype.label = function () {
    var t, tip, name;
    if (this.finishing) {
      t = 'Finishing voice input'; tip = 'Finishing the transcription…';
    } else if (this.listening) {
      name = ENGINE_NAMES[this.engine];
      t = 'Stop voice input'; tip = name ? t + ' (listening with ' + name + ')' : t;
    } else {
      name = ENGINE_NAMES[engineFor(this.field)];
      t = 'Start voice input'; tip = name ? t + ' (' + name + ')' : t;
    }
    this.btn.setAttribute('aria-label', t);
    this.btn.title = tip;
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

  Controller.prototype.spokenContext = function () {
    return compose(this.prefix || '', joinSpoken(this.finals || []), '').text.slice(-200);
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
    if (this.listening || this.finishing || this.btn.disabled || this.field.disabled || this.field.readOnly) return;
    if (active && active !== this) active.stop();
    active = this;
    this.clearMsg();
    this.rebase();
    this.listening = true;
    this.engine = engineFor(this.field);
    this.placeholder = this.field.getAttribute('placeholder');
    if (!this.field.value) this.field.setAttribute('placeholder', 'Listening…');
    this.btn.classList.add('cv-on');
    this.btn.setAttribute('aria-pressed', 'true');
    this.label();
    announce('Listening');
    this.armSilence();

    var self = this;
    var lang = (this.field.closest('[lang]') || document.documentElement).getAttribute('lang') || 'en-GB';
    var p = this.provider = (providers[this.engine] || providers.browser)({
      lang: lang, field: this.field, context: function () { return self.spokenContext(); }
    });
    p.onInterim = function (t) { if (self.provider !== p) return; self.interim = t || ''; if (t) self.heard(); self.render(); };
    p.onFinal = function (t) { if (self.provider !== p) return; self.interim = ''; if (t) { self.finals.push(t); self.heard(); } self.render(); };
    p.onState = function (s) {
      if (self.provider !== p) return;
      if (s === 'speech') self.heard();
      else if (s === 'transcribing') self.btn.classList.add('cv-busy');
      else if (s === 'transcribed') self.btn.classList.remove('cv-busy');
    };
    p.onNotice = function (t) { if (self.provider === p) self.showMsg(t); };
    p.onError = function (err) {
      if (self.provider !== p) return;
      var code = (err && err.code) || 'engine';
      self.end();
      if (code === 'switch') {
        self.refresh();
        self.start();
        self.showMsg(self.listening ? MESSAGES.switched : MESSAGES.serverDown);
        return;
      }
      self.showMsg(MESSAGES[code] || MESSAGES.engine);
    };
    try { p.start(); } catch (err) { p.onError({ code: 'engine' }); }
  };

  // Stop listening. An engine that is still transcribing what was said keeps
  // delivering text until it is done; this.finishing is set meanwhile.
  Controller.prototype.stop = function () {
    if (!this.listening) return;
    var p = this.provider;
    if (!p || typeof p.finish !== 'function') return this.end();
    this.listening = false;
    this.finishing = p;
    if (active === this) active = null;
    clearTimeout(this.silenceT); clearTimeout(this.speakT);
    this.btn.classList.remove('cv-on', 'cv-speaking');
    this.btn.classList.add('cv-busy');
    this.btn.setAttribute('aria-pressed', 'false');
    this.label();
    announce('Finishing transcription');
    var self = this;
    var done = function () { if (self.finishing === p) self.end(); };
    var guard = setTimeout(done, FLUSH_MAX_MS + 2000);
    var pr;
    try { pr = Promise.resolve(p.finish()); } catch (err) { pr = Promise.resolve(); }
    pr.then(done, done).then(function () { clearTimeout(guard); });
  };

  // End at once: no more text from the engine, whatever is on screen stays.
  Controller.prototype.end = function () {
    var p = this.provider, was = this.listening || !!this.finishing;
    this.provider = null;
    this.listening = false;
    this.finishing = null;
    if (active === this) active = null;
    clearTimeout(this.silenceT); clearTimeout(this.speakT);
    if (p) { try { p.stop(); } catch (err) { /* provider already stopped */ } }
    this.finals = []; this.interim = '';
    if (was) {
      if (this.placeholder == null) this.field.removeAttribute('placeholder');
      else this.field.setAttribute('placeholder', this.placeholder);
      announce('Stopped listening');
    }
    this.btn.classList.remove('cv-on', 'cv-speaking', 'cv-busy');
    this.btn.setAttribute('aria-pressed', 'false');
    this.label();
    var fn = this.resend;
    this.resend = null;
    if (fn) { try { fn(); } catch (err) { setTimeout(function () { throw err; }); } }
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
      c.resend = null; c.end(); c.clearMsg(); controllers.delete(c);
    });
  }

  function registerProvider(name, factory) {
    if (typeof name !== 'string' || !name || typeof factory !== 'function') throw new TypeError('registerProvider(name, factory)');
    providers[name] = factory;
    refreshAll();
  }

  function busyFor(test) {
    var hit = null;
    controllers.forEach(function (c) { if (!hit && (c.listening || c.finishing) && test(c)) hit = c; });
    return hit;
  }

  function loadConfig(done) {
    if (window.CHIPIN_VOICE || !SELF_SRC) return done();
    var s = document.createElement('script');
    try { s.src = new URL('voice-config.js', SELF_SRC).href; } catch (err) { return done(); }
    s.async = true;
    s.onload = s.onerror = function () { done(); };
    document.head.appendChild(s);
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

    // Stop before the page's own handler reads the field. If the engine is
    // still transcribing, hold the send and replay it once the text is in.
    document.addEventListener('submit', function (e) {
      var form = e.target, c = busyFor(function (x) { return x.form && x.form === form; });
      if (!c) return;
      c.stop();
      if (!c.finishing) return;
      e.preventDefault(); e.stopImmediatePropagation();
      var sub = e.submitter && e.submitter.form === form ? e.submitter : null;
      c.resend = function () {
        if (!form.isConnected) return;
        if (typeof form.requestSubmit === 'function') form.requestSubmit(sub && sub.isConnected ? sub : undefined);
        else form.submit();
      };
    }, true);
    document.addEventListener('click', function (e) {
      var t = e.target, c = busyFor(function (x) { return x.anchor && t && x.anchor.contains(t); });
      if (!c) return;
      c.stop();
      if (!c.finishing) return;
      e.preventDefault(); e.stopImmediatePropagation();
      var a = c.anchor;
      c.resend = function () { if (a.isConnected && !a.disabled) a.click(); };
    }, true);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && active) active.stop();
    });

    loadConfig(function () { checkEngine(true); });
    // Notice when the local backend connects or goes away after load.
    setInterval(function () {
      if (document.hidden) return;
      var key = candidateKey(candidate());
      if (key !== engine.key && !(engine.pending && engine.pendingKey === key)) checkEngine(true);
    }, 5000);
  }

  window.ChipVoice = Object.freeze({ registerProvider: registerProvider, attach: attach });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
