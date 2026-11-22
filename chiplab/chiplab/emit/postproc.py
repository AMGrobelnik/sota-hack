"""On-chip post-processing of the decision sequence, and channel-serial mode, for the streaming wrapper.

Both are optional blocks of compile-stream (emit/stream.py); without them the wrapper is unchanged, bit for bit.
Every parameter is fixed at compile time. Everything runs once per decision event:

  * a decision event is one streamed frame, or, in channel-serial mode, one cycle of C frames;
  * all state starts at zero after reset (the smoothing window is full of zeros).

channel_serial = {"channels": C, "reduce": "max"|"sum", "threshold": T, "output": name, "lane": 0}
  Each streamed frame carries ONE channel's input (the core's full input port set); the core is ONE per-channel
  model. Its score (output `output`, lane `lane`; default the first output, lane 0) is reduced over C consecutive
  frames into acc (running max or running sum, exact width, no overflow), and after the C-th frame
  decision = acc >= T, the outputs are registered and `valid` rises. One model copy instead of C copies.

postproc = {"output": name, "lane": 0, "threshold": S,
            "smooth": {"mode": "majority"|"kofn"|"average", "n": N, "k": K, "threshold": A},
            "min_duration": M, "hold": H}
  frame bit b:  output lane value >= S (without S: value != 0). In channel-serial mode b is the cycle decision
                and the value is acc (output, lane and threshold are then not allowed).
  smooth:       majority: at least K (default floor(N/2)+1) of the last N bits (this event included) are 1;
                kofn: at least k of the last N bits; average: the mean of the last N values >= A
                (sum >= A * N, exact). Without smooth the bit passes through.
  min_duration: the smoothed bit has been 1 for at least M consecutive events (a timer: e.g. a breathing pause
                of at least 20 s at one decision per second is M = 20). Default 1 (off).
  hold:         the alarm stays on for H more events after the timed bit falls (hysteresis). Default 0 (off).
  alarm = hold(duration(smooth(b))).

Output bits (bit 0 first; the Tiny Tapeout top shows the low 7 on uo_out[6:0]):
  postproc only:            alarm, then every core output bit as in the default wrapper;
  channel_serial only:      decision, then acc;
  channel_serial + postproc: alarm, decision, then acc.

reference() is the pure-Python model of all of this on frame sequences; the cocotb test (verify/rtlsim.py)
proves the RTL equals it, and prove-sequential (eqy) proves the RTL equals its gate netlist.
"""
from __future__ import annotations

import copy
import math

import numpy as np

SMOOTH_MODES = ("majority", "kofn", "average")
REDUCE = ("max", "sum")


class PostprocError(ValueError):
    pass


def _req(cond, msg):
    if not cond:
        raise PostprocError(msg)


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _clog2(n: int) -> int:
    return max(1, math.ceil(math.log2(n))) if n > 1 else 1


def _ubits(n: int) -> int:
    """Bits to hold 0..n unsigned."""
    return max(1, int(n).bit_length())


def _source(info: dict, output: str | None, lane, what: str) -> dict:
    outs = {o["name"]: o for o in info["outputs"]}
    name = output if output is not None else info["outputs"][0]["name"]
    _req(name in outs, f"{what}: unknown output {name!r}; outputs: {list(outs)}")
    lane = 0 if lane is None else lane
    _req(_int(lane) and 0 <= lane < outs[name]["lanes"], f"{what}: lane must be 0..{outs[name]['lanes'] - 1}")
    o = outs[name]
    return {"output": name, "lane": lane, "bits": o["bits"], "signed": bool(o.get("signed", False))}


def _range(bits: int, signed: bool) -> tuple[int, int]:
    return (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)


def normalize_channel_serial(cs: dict | None, info: dict) -> dict | None:
    if not cs:
        return None
    _req(isinstance(cs, dict), "channel_serial must be an object {channels, reduce, threshold}")
    extra = set(cs) - {"channels", "reduce", "threshold", "output", "lane"}
    _req(not extra, f"channel_serial: unknown keys {sorted(extra)}")
    C, red, T = cs.get("channels"), cs.get("reduce", "max"), cs.get("threshold")
    _req(_int(C) and 2 <= C <= 4096, "channel_serial.channels must be an int 2..4096")
    _req(red in REDUCE, "channel_serial.reduce must be max or sum")
    _req(_int(T), "channel_serial.threshold must be an int (decision = acc >= threshold)")
    src = _source(info, cs.get("output"), cs.get("lane"), "channel_serial")
    aw = src["bits"] if red == "max" else src["bits"] + _clog2(C)
    return {"channels": C, "reduce": red, "threshold": T, **src, "acc_bits": aw}


def normalize_postproc(pp: dict | None, info: dict, cs: dict | None = None) -> dict | None:
    if not pp:
        return None
    _req(isinstance(pp, dict), "postproc must be an object")
    extra = set(pp) - {"output", "lane", "threshold", "smooth", "min_duration", "hold"}
    _req(not extra, f"postproc: unknown keys {sorted(extra)}")
    out: dict = {}
    if cs:
        _req(all(pp.get(k) is None for k in ("output", "lane", "threshold")),
             "postproc: with channel_serial the input is the cycle decision (and acc); output, lane and threshold "
             "are not allowed")
        out.update({"source": "channel_serial", "value_bits": cs["acc_bits"], "value_signed": cs["signed"]})
    else:
        src = _source(info, pp.get("output"), pp.get("lane"), "postproc")
        S = pp.get("threshold")
        _req(S is None or _int(S), "postproc.threshold must be an int (frame bit = value >= threshold)")
        out.update({"source": "output", "output": src["output"], "lane": src["lane"], "threshold": S,
                    "value_bits": src["bits"], "value_signed": src["signed"]})
    sm = pp.get("smooth")
    if sm:
        _req(isinstance(sm, dict), "postproc.smooth must be an object {mode, n, ...}")
        extra = set(sm) - {"mode", "n", "k", "threshold"}
        _req(not extra, f"postproc.smooth: unknown keys {sorted(extra)}")
        mode, n = sm.get("mode"), sm.get("n")
        _req(mode in SMOOTH_MODES, f"postproc.smooth.mode must be one of {SMOOTH_MODES}")
        _req(_int(n) and 1 <= n <= 256, "postproc.smooth.n must be an int 1..256")
        s = {"mode": mode, "n": n}
        if mode == "majority":
            k = sm.get("k", sm.get("threshold", n // 2 + 1))
            _req(_int(k) and 1 <= k <= n, "postproc.smooth: majority threshold must be 1..n")
            s["k"] = k
        elif mode == "kofn":
            k = sm.get("k")
            _req(_int(k) and 1 <= k <= n, "postproc.smooth.k must be an int 1..n")
            s["k"] = k
        else:
            a = sm.get("threshold")
            _req(_int(a), "postproc.smooth.threshold must be an int (window mean >= threshold)")
            s["threshold"] = a
        out["smooth"] = s
    else:
        out["smooth"] = None
    M, H = pp.get("min_duration", 1), pp.get("hold", 0)
    _req(_int(M) and 1 <= M <= 1 << 20, "postproc.min_duration must be an int 1..1048576")
    _req(_int(H) and 0 <= H <= 1 << 20, "postproc.hold must be an int 0..1048576")
    out.update({"min_duration": M, "hold": H})
    return out


# ------------------------------------------------------------------------------------------------ reference model

def _alarm_seq(pp: dict, values: list[int], bits: list[int]) -> list[int]:
    """The post-processing state machine on one decision-event sequence (pure Python)."""
    sm, M, H = pp["smooth"], pp["min_duration"], pp["hold"]
    n = sm["n"] if sm else 1
    hist_b, hist_v = [0] * (n - 1), [0] * (n - 1)   # previous n-1 events, most recent first
    dc = hc = 0
    out = []
    for v, b in zip(values, bits):
        if sm is None:
            sb = b
        elif sm["mode"] == "average":
            sb = int(v + sum(hist_v) >= sm["threshold"] * n)
        else:
            sb = int(b + sum(hist_b) >= sm["k"])
        if n > 1:
            hist_b = [b] + hist_b[:-1]
            hist_v = [v] + hist_v[:-1]
        dc = min(dc + 1, M) if sb else 0
        db = int(dc >= M)
        out.append(int(db or hc > 0))
        hc = H if db else max(hc - 1, 0)
    return out


def reference(info: dict, outs: dict, postproc: dict | None = None, channel_serial: dict | None = None) -> dict:
    """Pure-Python model of the extended wrapper.

    info: the core's port info; outs: the core's outputs per streamed frame {name: int [F, lanes]} (ir.interp);
    postproc / channel_serial: as given to compile-stream. Returns {"event_frames": [frame index of every decision
    event], "fields": {name: [value per event]}, "packed": [all output bits per event as an int], "out_bits"}.
    """
    from chiplab.emit.stream import packed_outputs
    cs = normalize_channel_serial(channel_serial, info)
    pp = normalize_postproc(postproc, info, cs)
    _req(cs or pp, "nothing to model: give postproc and/or channel_serial")
    F = len(next(iter(outs.values())))
    fields: dict[str, list[int]] = {}
    if cs:
        s = [int(x) for x in np.asarray(outs[cs["output"]], dtype=np.int64)[:, cs["lane"]]]
        C, ev, acc_l, dec_l = cs["channels"], [], [], []
        acc = 0
        for f in range(F):
            acc = s[f] if f % C == 0 else (max(acc, s[f]) if cs["reduce"] == "max" else acc + s[f])
            if f % C == C - 1:
                ev.append(f); acc_l.append(acc); dec_l.append(int(acc >= cs["threshold"]))
        values, bits = acc_l, dec_l
        fields["decision"], fields["acc"] = dec_l, acc_l
    else:
        ev = list(range(F))
        values = [int(x) for x in np.asarray(outs[pp["output"]], dtype=np.int64)[:, pp["lane"]]]
        bits = [int(v >= pp["threshold"]) if pp["threshold"] is not None else int(v != 0) for v in values]
    if pp:
        fields["alarm"] = _alarm_seq(pp, values, bits)
    layout = out_fields(info, pp, cs)
    core = None
    if pp and not cs:
        core = packed_outputs(info, {k: np.asarray(v)[ev] for k, v in outs.items()}) if ev else []
    packed = []
    for e in range(len(ev)):
        acc_v, sh = 0, 0
        for name, w in layout:
            v = int(core[e]) if name == "core" else fields[name][e]
            acc_v |= (v & ((1 << w) - 1)) << sh
            sh += w
        packed.append(acc_v)
    return {"event_frames": ev, "fields": fields, "packed": packed, "out_bits": sum(w for _, w in layout)}


def out_fields(info: dict, pp: dict | None, cs: dict | None) -> list[tuple[str, int]]:
    """[(field, width)] from bit 0 up; field "core" is every core output bit in the default order."""
    ob = sum(o["lanes"] * o["bits"] for o in info["outputs"])
    f = []
    if pp:
        f.append(("alarm", 1))
    if cs:
        f += [("decision", 1), ("acc", cs["acc_bits"])]
    elif pp:
        f.append(("core", ob))
    return f


# ------------------------------------------------------------------------------------------------ RTL

def _lit(v: int, w: int) -> str:
    """A w-bit signed constant in two's complement."""
    return f"$signed({w}'h{v % (1 << w):x})"


def _sx(expr: str, w: int, signed: bool, W: int) -> str:
    """Extend a w-bit vector (signed or not) to a W-bit signed expression."""
    if W == w:
        return f"$signed({expr})"
    pad = f"{{{W - w}{{{expr}[{w - 1}]}}}}" if signed and w > 1 else (f"{{{W - w}{{{expr}}}}}" if signed else f"{W - w}'d0")
    return f"$signed({{{pad}, {expr}}})"


def _zx(expr: str, w: int, W: int) -> str:
    return expr if W == w else f"{{{W - w}'d0, {expr}}}"


def _cmp_width(vw: int, signed: bool, *consts: int) -> int:
    lo, hi = _range(vw, signed)
    m = max([abs(lo), abs(hi)] + [abs(c) for c in consts])
    return m.bit_length() + 2


class Extension:
    """The RTL of the post-processing and channel-serial blocks, for emit_stream to splice into the wrapper."""

    def __init__(self, info: dict, postproc: dict | None, channel_serial: dict | None, tt: bool = True):
        self.info = info
        self.cs = normalize_channel_serial(channel_serial, info)
        self.pp = normalize_postproc(postproc, info, self.cs)
        self.fields = out_fields(info, self.pp, self.cs)
        self.out_bits = sum(w for _, w in self.fields)
        self.visible = min(self.out_bits, 7) if tt else self.out_bits     # bits held in the output register

    def _lane_offset(self, output: str, lane: int) -> tuple[int, int]:
        off = 0
        for o in self.info["outputs"]:
            if o["name"] == output:
                return off + lane * o["bits"], o["bits"]
            off += o["lanes"] * o["bits"]
        raise PostprocError(f"unknown output {output!r}")

    def _src(self, output: str, lane: int) -> str:
        """The bits of one output lane inside the packed core output vector `cout`."""
        lo, w = self._lane_offset(output, lane)
        return f"cout[{lo + w - 1}:{lo}]" if w > 1 else f"cout[{lo}]"

    def _field_offset(self, name: str) -> int:
        off = 0
        for n, w in self.fields:
            if n == name:
                return off
            off += w
        raise PostprocError(name)

    def _history(self):
        """The smoothing window's history entries (the previous n-1 events), newest first.

        The newest entry is what the output register captured at the last event wherever it holds that bit (the
        decision, the score, the 1-bit core output): one flip-flop per value, never two holding the same bit, which
        synthesis would merge anyway and which a register-matching equivalence proof cannot pair. Returns
        (entry width, [(source bit, output-register bit or None)] for the newest entry) or None without a window.
        """
        sm = self.pp["smooth"] if self.pp else None
        if not sm or sm["n"] == 1:
            return None
        avg = sm["mode"] == "average"
        if self.cs:
            w = self.cs["acc_bits"] if avg else 1
            base = self._field_offset("acc" if avg else "decision")
            name = "cs_new" if avg else "cs_dec"
        else:
            w = self.pp["value_bits"] if avg else 1
            lo, _ = self._lane_offset(self.pp["output"], self.pp["lane"])
            stored = avg or (self.pp["threshold"] is None and self.pp["value_bits"] == 1)   # pp_b = |pp_v = pp_v
            base = self._field_offset("core") + lo if stored else None
            name = "pp_v" if avg else "pp_b"
        bits = []
        for i in range(w):
            src = f"{name}[{i}]" if w > 1 else name
            idx = base + i if base is not None and base + i < self.visible else None
            bits.append((src, idx))
        return w, bits

    def decls(self) -> list[str]:
        """Wires and registers, after `cout` is declared; defines ev (decision event) and xout (output bits)."""
        L, cs, pp = [], self.cs, self.pp
        if cs:
            C, aw, vw, sg = cs["channels"], cs["acc_bits"], cs["bits"], cs["signed"]
            ccw = _clog2(C)
            L += [f"  reg [{ccw - 1}:0] cs_ch;", f"  reg [{aw - 1}:0] cs_acc;",
                  f"  wire [{vw - 1}:0] cs_v = {self._src(cs['output'], cs['lane'])};"]
            if aw == vw:
                L.append(f"  wire [{aw - 1}:0] cs_s = cs_v;")
            else:
                L.append(f"  wire [{aw - 1}:0] cs_s = {_sx('cs_v', vw, sg, aw)};" if sg else f"  wire [{aw - 1}:0] cs_s = {_zx('cs_v', vw, aw)};")
            if cs["reduce"] == "max":
                gt = f"($signed(cs_s) > $signed(cs_acc))" if sg else "(cs_s > cs_acc)"
                red = f"({gt} ? cs_s : cs_acc)"
            else:
                red = "(cs_acc + cs_s)"
            W = _cmp_width(aw, sg, cs["threshold"])
            L += [f"  wire [{aw - 1}:0] cs_new = (cs_ch == {ccw}'d0) ? cs_s : {red};",
                  f"  wire cs_last = (cs_ch == {ccw}'d{C - 1});",
                  f"  wire cs_dec = {_sx('cs_new', aw, sg, W)} >= {_lit(cs['threshold'], W)};",
                  "  wire ev = done & cs_last;"]
            vname, vw2, vsg, bname = "cs_new", aw, sg, "cs_dec"
        else:
            L.append("  wire ev = done;")
        if pp:
            if not cs:
                vw2, vsg = pp["value_bits"], pp["value_signed"]
                L.append(f"  wire [{vw2 - 1}:0] pp_v = {self._src(pp['output'], pp['lane'])};")
                vname = "pp_v"
                if pp["threshold"] is not None:
                    W = _cmp_width(vw2, vsg, pp["threshold"])
                    L.append(f"  wire pp_b = {_sx('pp_v', vw2, vsg, W)} >= {_lit(pp['threshold'], W)};")
                else:
                    L.append("  wire pp_b = |pp_v;")
                bname = "pp_b"
            sm = pp["smooth"]
            n = sm["n"] if sm else 1
            hist = self._history()
            if hist:   # pp_w0 = newest history entry (output-register bits + pp_h0), pp_w1.. = older entries
                w, bits = hist
                own = [src for src, idx in bits if idx is None]
                if own:
                    L.append(f"  reg [{len(own) - 1}:0] pp_h0;")
                k, parts = len(own), []
                for src, idx in reversed(bits):          # MSB first
                    if idx is None:
                        k -= 1
                        parts.append(f"pp_h0[{k}]")
                    else:
                        parts.append(f"oreg[{idx}]")
                L.append(f"  wire [{w - 1}:0] pp_w0 = {{{', '.join(parts)}}};" if len(parts) > 1 else
                         f"  wire [{w - 1}:0] pp_w0 = {parts[0]};")
                L += [f"  reg [{w - 1}:0] pp_w{i};" for i in range(1, n - 1)]
            if sm is None or n == 1 and sm["mode"] != "average":
                L.append(f"  wire pp_sb = {bname};" if sm is None or sm["k"] == 1 else "  wire pp_sb = 1'b0;")
            elif sm["mode"] == "average":
                W = _cmp_width(vw2, vsg, sm["threshold"] * n) + _clog2(n)
                terms = [_sx(vname, vw2, vsg, W)] + [_sx(f"pp_w{i}", vw2, vsg, W) for i in range(n - 1)]
                L += [f"  wire signed [{W - 1}:0] pp_sum = {' + '.join(terms)};",
                      f"  wire pp_sb = pp_sum >= {_lit(sm['threshold'] * n, W)};"]
            else:
                PW = _ubits(n)
                terms = [_zx(bname, 1, PW)] + [_zx(f"pp_w{i}", 1, PW) for i in range(n - 1)]
                L += [f"  wire [{PW - 1}:0] pp_cnt = {' + '.join(terms)};",
                      f"  wire pp_sb = pp_cnt >= {PW}'d{sm['k']};"]
            M, H = pp["min_duration"], pp["hold"]
            if M > 1:
                DW = _ubits(M)
                L += [f"  reg [{DW - 1}:0] pp_dc;",
                      f"  wire [{DW - 1}:0] pp_dn = pp_sb ? ((pp_dc == {DW}'d{M}) ? pp_dc : pp_dc + {DW}'d1) : {DW}'d0;",
                      f"  wire pp_db = (pp_dn == {DW}'d{M});"]
            else:
                L.append("  wire pp_db = pp_sb;")
            if H > 0:
                HW = _ubits(H)
                L += [f"  reg [{HW - 1}:0] pp_hc;", f"  wire alarm = pp_db | (pp_hc != {HW}'d0);"]
            else:
                L.append("  wire alarm = pp_db;")
        parts = {"alarm": "alarm", "decision": "cs_dec", "acc": "cs_new", "core": "cout"}
        cat = [parts[n] for n, _ in reversed(self.fields)]
        L.append(f"  wire [{self.out_bits - 1}:0] xout = {{{', '.join(cat)}}};" if len(cat) > 1 else
                 f"  wire [{self.out_bits - 1}:0] xout = {cat[0]};")
        return L

    def wires(self) -> list[str]:
        """Names of the combinational wires these blocks add (registers excluded). Sequential equivalence must not
        cut the proof at them: synthesis may compute one from another in the opposite direction (e.g. the timer's
        next state from `alarm`), and a cut there loses the relation between the two."""
        import re
        return [m.group(1) for line in self.decls()
                if (m := re.match(r"\s*wire (?:signed )?(?:\[[^\]]+\] )?(\w+)", line))]

    def reset(self) -> str:
        r = []
        if self.cs:
            r += [f"cs_ch <= {_clog2(self.cs['channels'])}'d0;", f"cs_acc <= {self.cs['acc_bits']}'d0;"]
        pp = self.pp
        if pp:
            hist = self._history()
            if hist:
                w, bits = hist
                own = sum(1 for _, idx in bits if idx is None)
                r += ([f"pp_h0 <= {own}'d0;"] if own else []) + [f"pp_w{i} <= {w}'d0;" for i in range(1, pp["smooth"]["n"] - 1)]
            if pp["min_duration"] > 1:
                r.append(f"pp_dc <= {_ubits(pp['min_duration'])}'d0;")
            if pp["hold"] > 0:
                r.append(f"pp_hc <= {_ubits(pp['hold'])}'d0;")
        return " ".join(r)

    def on_done(self, obt: int) -> list[str]:
        """Statements inside the clock-enabled branch, replacing the default `if (done) ...` line."""
        L = []
        if self.cs:
            C = self.cs["channels"]
            ccw = _clog2(C)
            L += ["      if (done) begin",
                  f"        if (cs_last) cs_ch <= {ccw}'d0; else begin cs_ch <= cs_ch + {ccw}'d1; cs_acc <= cs_new; end",
                  "      end"]
        L += ["      if (ev) begin", f"        oreg <= xout[{obt - 1}:0]; valid <= 1'b1;"]
        pp = self.pp
        if pp:
            hist = self._history()
            if hist:
                n = pp["smooth"]["n"]
                own = [src for src, idx in hist[1] if idx is None]
                sh = ([f"pp_h0 <= {{{', '.join(reversed(own))}}};" if len(own) > 1 else f"pp_h0 <= {own[0]};"] if own else [])
                sh += [f"pp_w{i} <= pp_w{i - 1};" for i in range(1, n - 1)]
                if sh:
                    L.append("        " + " ".join(sh))
            if pp["min_duration"] > 1:
                L.append("        pp_dc <= pp_dn;")
            if pp["hold"] > 0:
                HW = _ubits(pp["hold"])
                L.append(f"        pp_hc <= pp_db ? {HW}'d{pp['hold']} : ((pp_hc != {HW}'d0) ? pp_hc - {HW}'d1 : {HW}'d0);")
        L.append("      end")
        return L

    def bitmap(self, core_bitmap: list[dict]) -> list[dict]:
        out = []
        for name, w in self.fields:
            out += core_bitmap if name == "core" else [{"output": name, "lane": 0, "bit": b} for b in range(w)]
        return out

    def summary(self) -> dict:
        s = {"postproc": self.pp, "channel_serial": self.cs, "output_fields": [{"name": n, "bits": w} for n, w in self.fields]}
        s["frames_per_decision"] = self.cs["channels"] if self.cs else 1
        return s


# ------------------------------------------------------------------------------------------------ parallel baseline

def parallel_ir(core_ir: dict, channel_serial: dict, name: str | None = None) -> dict:
    """The parallel-fusion version of a channel-serial chip: C copies of the core (one input port set per channel,
    ports named ch<i>_<port>), their scores reduced by a max (or sum) tree and compared with the threshold. Same
    outputs as the channel-serial wrapper: decision, then acc. Used as the area baseline and as a cross-check."""
    from chiplab.emit.verilog import emit
    from chiplab.ingest.compose import compose
    from chiplab.ir.schema import validate
    info = emit(core_ir)[1]
    cs = normalize_channel_serial(channel_serial, info)
    C = cs["channels"]
    ir = compose({f"ch{i}": copy.deepcopy(core_ir) for i in range(C)}, [], shared_inputs=False,
                 name=name or f"{core_ir.get('name', 'core')}_x{C}_{cs['reduce']}")
    src = {o["name"]: o["src"] for o in ir["outputs"]}
    nodes = ir["nodes"]
    for i in range(C):
        nodes.append({"id": f"par_s{i}", "op": "gather", "src": src[f"ch{i}_{cs['output']}"], "idx": [cs["lane"]]})
    nodes.append({"id": "par_all", "op": "concat", "srcs": [f"par_s{i}" for i in range(C)]})
    if cs["reduce"] == "max":
        nodes.append({"id": "par_acc", "op": "max", "src": "par_all", "groups": [list(range(C))]})
    else:
        nodes.append({"id": "par_acc", "op": "matvec", "src": "par_all", "W": [[1] * C]})
    nodes.append({"id": "par_dec", "op": "cmp", "src": "par_acc", "rel": "ge", "t": [cs["threshold"]]})
    ir["outputs"] = [{"name": "decision", "src": "par_dec"}, {"name": "acc", "src": "par_acc"}]
    return validate(ir)


def channel_frames(X: dict, channels: int) -> dict:
    """Parallel inputs {ch<i>_<port>: [N, lanes]} -> channel-serial frames {port: [N*C, lanes]} (channel 0 first)."""
    ports = sorted({k.split("_", 1)[1] for k in X})
    N = len(next(iter(X.values())))
    return {p: np.stack([np.asarray(X[f"ch{i}_{p}"]) for i in range(channels)], axis=1).reshape(N * channels, -1)
            for p in ports}


# ------------------------------------------------------------------------------------------------ area

def _ff_gates(by_type: dict) -> tuple[int, int]:
    ff = sum(v for k, v in by_type.items() if "DFF" in k or "DLATCH" in k)
    gates = sum(v for k, v in by_type.items() if "DFF" not in k and "DLATCH" not in k and k != "$_BUF_")
    return ff, gates


def area_compare(core_ir: dict, channel_serial: dict | None, workdir, postproc: dict | None = None,
                 timeout: int = 900) -> dict:
    """Synthesise (Yosys, simple 2-input gates) the Tiny Tapeout streaming chip with these options and, in
    channel-serial mode, the parallel-fusion chip (C copies of the core) streamed the same way. Flip-flops and
    combinational gates are counted separately."""
    from pathlib import Path
    from chiplab.emit.stream import emit_stream
    from chiplab.hw.yosys import synth_generic
    wd = Path(workdir).resolve(); wd.mkdir(parents=True, exist_ok=True)

    def one(tag, ir, **kw):
        text, sinfo = emit_stream(ir, tt=True, **kw)
        (wd / f"{tag}.v").write_text(text)
        r = synth_generic(wd / f"{tag}.v", sinfo["top"], wd / tag, timeout=timeout)
        ff, g = _ff_gates(r["cells_by_type"])
        return {"flip_flops": ff, "gates": g, "top": sinfo["top"], "transfers_per_frame": sinfo["transfers_per_frame"]}
    out = {"basis": "Yosys synth -flatten + ABC to simple 2-input gates; flip-flops counted apart from gates",
           "serial": one("serial", core_ir, postproc=postproc, channel_serial=channel_serial)}
    if channel_serial:
        par = parallel_ir(core_ir, channel_serial)
        out["parallel"] = one("parallel", par, postproc=None, channel_serial=None)
        if postproc:
            out["parallel"]["note"] = "parallel version without the post-processing block"
        out["parallel"]["copies_of_core"] = channel_serial["channels"]
        s, p = out["serial"], out["parallel"]
        out["gate_ratio_parallel_over_serial"] = round(p["gates"] / max(1, s["gates"]), 3)
        out["ff_ratio_parallel_over_serial"] = round(p["flip_flops"] / max(1, s["flip_flops"]), 3)
    return out
