"""Streaming wrapper: a clocked shell around the combinational core for pin-limited packages.

Tiny Tapeout has 8 inputs, 8 outputs and 8 bidirectional pins, so a chip with tens of input lanes cannot take
them in parallel. Protocol (documented for the scientist and the testbench):

  * one 15-bit word per strobe: data = {uio_in[7:0], ui_in[6:0]} (uio pins are inputs, uio_oe = 0);
  * strobe = ui_in[7]; the wrapper synchronises it (2 flip-flops) and acts on its rising edge, so data must be
    stable from the strobe's rising edge until 3 clock cycles later;
  * order: every lane of input port 0 (lane 0 first), then port 1, ...; a lane wider than 15 bits takes
    ceil(bits/15) words, least-significant 15 bits first; values are two's complement when signed;
  * after the last word of a frame, the core's outputs are registered one cycle later and `valid`
    (uo_out[7]) goes high and stays high (level) until the first word of the next frame;
  * uo_out[6:0] = the low 7 bits of all output ports concatenated (port 0 at bit 0); if the outputs need more
    than 7 bits the extra bits are not visible on the Tiny Tapeout pins (reported as `truncated` in the info).
  * rst_n is a synchronous active-low reset; nothing changes while ena is low.

The generic (non-TT) variant has plain ports (clk, rst_n, strobe, din[14:0], dout[all output bits], valid),
for FPGA boards and for tools that want every output bit.
"""
from __future__ import annotations

import math

import numpy as np

from chiplab.emit.verilog import emit
from chiplab.ir.schema import design_id

WORD = 15


def transfers(info: dict) -> list[tuple[str, int, int, int]]:
    """[(port, lane, chunk, width)] in streaming order."""
    out = []
    for p in info["inputs"]:
        n = math.ceil(p["bits"] / WORD)
        for i in range(p["lanes"]):
            for c in range(n):
                out.append((p["name"], i, c, min(WORD, p["bits"] - c * WORD)))
    return out


def _clog2(n: int) -> int:
    return max(1, math.ceil(math.log2(n))) if n > 1 else 1


def emit_stream(core_ir: dict, core_info: dict | None = None, tt: bool = True, core_text: str | None = None) -> tuple[str, dict]:
    """Return (verilog with the core and the wrapper, info). info lists the protocol and the output bit map."""
    if core_text is not None:  # an alternative implementation of the same core (e.g. the alkaid-optimised RTL)
        info = core_info or emit(core_ir)[1]
    else:
        core_text, info = emit(core_ir) if core_info is None else (emit(core_ir)[0], core_info)
    did = design_id(core_ir)
    top = f"tt_um_chipin_{did}" if tt else f"chipin_{did}_stream"
    tr = transfers(info)
    T = len(tr)
    CW = _clog2(T)
    ob = sum(o["lanes"] * o["bits"] for o in info["outputs"])
    obt = min(ob, 7) if tt else ob
    idx = {}
    for t, (p, i, c, w) in enumerate(tr):
        idx[(p, i, c)] = (t, w)
    L = []
    if tt:
        L += [f"module {top} (", "  input  wire [7:0] ui_in,", "  output wire [7:0] uo_out,", "  input  wire [7:0] uio_in,",
              "  output wire [7:0] uio_out,", "  output wire [7:0] uio_oe,", "  input  wire       ena,",
              "  input  wire       clk,", "  input  wire       rst_n", ");",
              "  wire [14:0] din = {uio_in, ui_in[6:0]};", "  wire strobe_pin = ui_in[7];", "  wire en = ena;"]
    else:
        L += [f"module {top} (", "  input  wire        clk,", "  input  wire        rst_n,", "  input  wire        strobe,",
              "  input  wire [14:0] din,", f"  output wire [{ob - 1}:0] dout,", "  output wire        valid_o", ");",
              "  wire strobe_pin = strobe;", "  wire en = 1'b1;"]
    L += [f"  reg [{WORD * T - 1}:0] sreg;", f"  reg [{CW - 1}:0] cnt;", "  reg s1, s2, s3, done, valid;",
          f"  reg [{obt - 1}:0] oreg;", "  wire stb = s2 & ~s3;"]
    used = set()
    conns = []
    for p in info["inputs"]:
        n = math.ceil(p["bits"] / WORD)
        parts = []
        for i in reversed(range(p["lanes"])):
            for c in reversed(range(n)):
                t, w = idx[(p["name"], i, c)]
                parts.append(f"sreg[{WORD * t + w - 1}:{WORD * t}]" if w > 1 else f"sreg[{WORD * t}]")
                used.update(range(WORD * t, WORD * t + w))
        L.append(f"  wire [{p['lanes'] * p['bits'] - 1}:0] cin_{p['name']} = {{{', '.join(parts)}}};")
        conns.append(f".{p['name']}(cin_{p['name']})")
    for o in info["outputs"]:
        L.append(f"  wire [{o['lanes'] * o['bits'] - 1}:0] cout_{o['name']};")
        conns.append(f".{o['name']}(cout_{o['name']})")
    L.append(f"  {info['top']} core ({', '.join(conns)});")
    cat = [f"cout_{o['name']}" for o in reversed(info["outputs"])]
    L.append(f"  wire [{ob - 1}:0] cout = {{{', '.join(cat)}}};" if len(cat) > 1 else f"  wire [{ob - 1}:0] cout = {cat[0]};")
    shift = f"{{din, sreg[{WORD * T - 1}:{WORD}]}}" if T > 1 else "din"
    L += ["  always @(posedge clk) begin",
          "    if (!rst_n) begin",
          f"      sreg <= {WORD * T}'d0; cnt <= {CW}'d0; s1 <= 1'b0; s2 <= 1'b0; s3 <= 1'b0;",
          f"      done <= 1'b0; valid <= 1'b0; oreg <= {obt}'d0;",
          "    end else if (en) begin",
          "      s1 <= strobe_pin; s2 <= s1; s3 <= s2;",
          "      done <= 1'b0;",
          "      if (stb) begin",
          f"        sreg <= {shift};",
          f"        if (cnt == {CW}'d{T - 1}) begin cnt <= {CW}'d0; done <= 1'b1; end else cnt <= cnt + {CW}'d1;",
          f"        if (cnt == {CW}'d0) valid <= 1'b0;",
          "      end",
          f"      if (done) begin oreg <= cout[{obt - 1}:0]; valid <= 1'b1; end",
          "    end",
          "  end"]
    unused = [f"sreg[{b}]" for b in range(WORD * T) if b not in used]
    if tt:
        pad = f"{7 - obt}'d0, " if obt < 7 else ""
        L += [f"  assign uo_out = {{valid, {pad}oreg}};", "  assign uio_out = 8'd0;", "  assign uio_oe = 8'd0;"]
        if ob > obt:
            unused.append(f"cout[{ob - 1}:{obt}]")
    else:
        L += ["  assign dout = oreg;", "  assign valid_o = valid;"]
    if unused:
        L.append(f"  wire _unused = &{{1'b0, {', '.join(unused)}}};")
    L += ["endmodule", ""]
    text = core_text + "\n" + "\n".join(L)
    bitmap = []
    for o in info["outputs"]:
        for i in range(o["lanes"]):
            for b in range(o["bits"]):
                bitmap.append({"output": o["name"], "lane": i, "bit": b})
    sinfo = {"top": top, "core_top": info["top"], "tt": tt, "word_bits": WORD, "transfers_per_frame": T,
             "counter_bits": CW, "output_bits": ob, "visible_output_bits": obt, "truncated": ob > obt,
             "uo_map": bitmap[:obt] if tt else bitmap, "core": info,
             "protocol": "15-bit word = {uio_in, ui_in[6:0]} per rising edge of ui_in[7]; hold data 3 cycles; "
                         "valid = uo_out[7] (level), outputs on uo_out[6:0]" if tt else
                         "15-bit din per rising edge of strobe; hold 3 cycles; valid_o level; dout = all output bits"}
    return text, sinfo


def frame_words(info: dict, X: dict) -> np.ndarray:
    """Integer inputs {port: [N, lanes]} -> words [N, T] in streaming order."""
    tr = transfers(info)
    bits = {p["name"]: p["bits"] for p in info["inputs"]}
    N = len(next(iter(X.values())))
    W = np.zeros((N, len(tr)), dtype=np.int64)
    for t, (p, i, c, w) in enumerate(tr):
        v = np.asarray(X[p], dtype=np.int64)[:, i] & ((1 << bits[p]) - 1)
        W[:, t] = (v >> (c * WORD)) & ((1 << w) - 1)
    return W


def packed_outputs(info: dict, outs: dict, nbits: int | None = None) -> np.ndarray:
    """Interpreter outputs {name: [N, lanes]} -> the packed output bit vector as integers (low nbits)."""
    acc, sh = None, 0
    for o in info["outputs"]:
        v = np.asarray(outs[o["name"]], dtype=np.int64)
        for i in range(o["lanes"]):
            lane = (v[:, i] & ((1 << o["bits"]) - 1)).astype(object)
            acc = lane * (1 << sh) if acc is None else acc + lane * (1 << sh)
            sh += o["bits"]
    if nbits is not None:
        acc = acc % (1 << nbits)
    return acc
