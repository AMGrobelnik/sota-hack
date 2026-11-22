"""Model ingest: every supported model format becomes one chipir/1 document.

Formats: chipir JSON (chipir.py), intnn integer parameters (intnn.py), torchlogix logic-gate networks
(torchlogix.py), TreeLUT / XGBoost tree ensembles (treelut.py). Several models can be composed into one
multi-output chip with fusion logic (compose.py).
"""
from chiplab.ingest.chipir import load as load_chipir  # noqa: F401
