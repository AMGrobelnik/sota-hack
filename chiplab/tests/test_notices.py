"""The lab ships its own licence (MIT) and the licences of what it uses."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_licence_files():
    lic = (ROOT / "LICENSE").read_text()
    assert lic.startswith("MIT License") and "Permission is hereby granted" in lic
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    for name, licence in (("alkaid", "LGPL-3.0"), ("torchlogix", "MIT"), ("Yosys", "ISC"), ("LibreLane", "Apache-2.0"),
                          ("sky130 PDK", "Apache-2.0"), ("TreeLUT", "MIT")):
        assert any(name in line and licence in line for line in notices.splitlines()), (name, licence)
