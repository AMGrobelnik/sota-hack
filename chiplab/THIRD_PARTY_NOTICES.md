# Third-party notices

The chip lab's own code is under the MIT licence (see `LICENSE`). It uses the projects below as published, under
their own licences. Licences were read from each package's metadata or its repository (November 2026).

## Python dependencies (installed by uv, not vendored)

| Package | Licence | Use |
|---|---|---|
| alkaid 0.8.2 (optional) | LGPL-3.0-or-later | adder graphs |
| torchlogix 0.2.2 (optional) | MIT | gate networks |
| NumPy | BSD-3-Clause | numerics |
| SciPy | BSD-3-Clause | numerics |
| PyTorch | BSD-3-Clause | training |
| PyYAML | MIT | config |
| scikit-learn | BSD-3-Clause | models |
| Huey | MIT | job queue |
| diskcache | Apache-2.0 | result cache |
| Jinja2 | BSD-3-Clause | reports |
| pyvcd | MIT | VCD traces |
| XGBoost | Apache-2.0 | tree models |
| cocotb (optional) | BSD-3-Clause | testbenches |
| pytest (dev) | MIT | tests |
| MCP Python SDK (optional) | MIT | MCP server |
| sse-starlette (optional) | BSD-3-Clause | MCP server |
| uvicorn (optional) | BSD-3-Clause | MCP server |
| wfdb (optional) | MIT | datasets |

alkaid is an optional extra (`ingest`), used as a separate, unmodified package: the lab calls it in its own worker
process (`chiplab/emit/alkaid_worker.py`) and never copies its source into this repository.

timescoring (MIT, the EPFL epilepsy performance metrics) is not a dependency of the chip lab; if a seizure
scoring step adds it, it is used as an unmodified package under that licence.

## Vendored code

| Project | Licence | Where |
|---|---|---|
| TreeLUT | MIT | `chiplab/ingest/vendor/treelut` |

## Tools run as separate programs (not distributed here)

| Tool | Licence | Use |
|---|---|---|
| Yosys | ISC | synthesis |
| LibreLane | Apache-2.0 | layout (container) |
| sky130 PDK | Apache-2.0 | standard cells |
| gf180mcu PDK | Apache-2.0 | standard cells |
| IHP SG13G2 PDK | Apache-2.0 | standard cells |
| open_pdks | Apache-2.0 | PDK install |

`README.md` section 11 lists the other tools of the OSS CAD Suite and the LibreLane image.

## Generated RTL

RTL from the default emitter contains no third-party code. RTL from `optimizer: alkaid` made before the clean
emitter carries copies of alkaid's LGPL-3.0 Verilog helper modules (`chipin_alk_*`); `tt_package`, `tt_readiness`
and `tt_export` refuse such RTL for Tiny Tapeout, which requires Apache-2.0. Once the clean emitter lands,
generated RTL contains no third-party code.
