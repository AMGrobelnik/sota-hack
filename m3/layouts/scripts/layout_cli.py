"""`chiplab` CLI with the gf180 3.3 V library selection fixed for LibreLane 3 (see ../proposed/gf180-lib.patch).

The lab's _GF180_33V sets LIB_SYNTH / LIB_FASTEST / LIB_SLOWEST, which LibreLane 3.0.14 no longer reads; LIB keeps
the PDK's 5 V corners while DEFAULT_CORNER asks for 3v30, so synthesis gets no liberty file
("ERROR: Missing `-liberty liberty_file' option!"). This sets LIB per 3.3 V corner instead; nothing else changes.
"""
from __future__ import annotations

import sys

from chiplab.hw import librelane

_SC = "pdk_dir::libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__"
librelane._GF180_33V.clear()
librelane._GF180_33V.update({
    "VDD_PIN_VOLTAGE": 3.3,
    "LIB": {"*_tt_025C_3v30": [_SC + "tt_025C_3v30.lib"], "*_ss_125C_3v00": [_SC + "ss_125C_3v00.lib"],
            "*_ff_n40C_3v60": [_SC + "ff_n40C_3v60.lib"]},
    "DEFAULT_CORNER": "nom_tt_025C_3v30",
    "STA_CORNERS": ["nom_tt_025C_3v30", "nom_ss_125C_3v00", "nom_ff_n40C_3v60"],
})

if __name__ == "__main__":
    from chiplab.cli import main
    sys.exit(main())
