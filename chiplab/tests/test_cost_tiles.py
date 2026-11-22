"""Tiny Tapeout tile sizing per PDK and the manufacturing-route fit checks (pure arithmetic, no tools needed)."""
from __future__ import annotations

import pytest

from chiplab.hw import cost, tinytapeout as tt
from chiplab.hw.cost import ROUTES, WAFERSPACE_SLOTS, estimate, tt_tiles_for, waferspace_slot


def _route(r: dict, rid: str) -> dict:
    return next(e for e in r["routes"] if e["route"] == rid)


# ------------------------------------------------------------------------------------------- tiles per PDK

def test_tile_sizes_follow_tt_support_tools_yaml():
    assert tt.TILE_SIZES["sky130A"]["1x1"] == (161.0, 111.52)
    assert tt.TILE_SIZES["gf180mcuD"]["1x1"] == (346.64, 160.72)
    assert tt.TILE_SIZES["gf180mcuD"]["4x8"] == (1440.32, 1560.16)
    assert tt.TILE_SIZES["ihp-sg13g2"]["1x1"] == (202.08, 154.98)
    assert list(tt.tile_sizes("gf180mcuD"))[-1] == "4x8"
    assert list(tt.tile_sizes("ihp-sg13g2"))[-1] == "8x4"
    assert tt.TILE_UM is tt.TILE_SIZES["sky130A"]          # old name still the sky130 table
    assert list(tt.TILE_UM)[-1] == "8x2"


@pytest.mark.parametrize("pdk", list(tt.TILE_SIZES))
def test_tile_sizes_ordered_by_tile_count_then_area(pdk):
    keys = list(tt.tile_sizes(pdk))
    n = [int(k.split("x")[0]) * int(k.split("x")[1]) for k in keys]
    assert n == sorted(n) and keys[0] == "1x1"


def test_smallest_tile_uses_the_pdk_tile():
    # 25,000 um2 of cells at 55%: one GF180 tile (30,641 um2 usable) but a 2x2 block of sky130 tiles
    assert tt.smallest_tile(25_000, "gf180mcuD") == "1x1"
    assert tt.smallest_tile(25_000, "sky130A") == "2x2"
    assert tt.smallest_tile(25_000, "ihp-sg13g2") == "1x2"
    # 0.5 mm2: beyond sky130's 8x2 (about 0.31 mm2 of tile) but fine on GF180
    assert tt.smallest_tile(500_000 * 0.55, "sky130A") is None
    assert tt.smallest_tile(500_000 * 0.55, "gf180mcuD") == "3x4"
    assert tt.smallest_tile(10e6, "gf180mcuD") is None
    with pytest.raises(ValueError):
        tt.tile_sizes("tsmc7")


@pytest.mark.parametrize("pdk,expect", [("sky130A", "2x2"), ("gf180mcuD", "1x1"), ("ihp-sg13g2", "1x2")])
def test_pick_tiles_per_pdk(monkeypatch, tmp_path, pdk, expect):
    import chiplab.hw.pdk as pdkmod
    seen = {}

    def fake_map(rtl, top, workdir, key, *a, **k):
        seen["key"] = key
        return {"area_um2": 25_000.0}
    monkeypatch.setattr(pdkmod, "map_to_process", fake_map)
    (tmp_path / "a.v").write_text("module top; endmodule\n")
    r = tt.pick_tiles([tmp_path / "a.v"], "top", tmp_path / "w", pdk)
    assert r["tiles"] == expect
    assert seen["key"] == {"sky130A": "sky130", "gf180mcuD": "gf180", "ihp-sg13g2": "ihp"}[pdk]
    w, h = tt.TILE_SIZES[pdk][expect]
    assert r["tile_area_um2"] == round(w * h, 1)


def test_pick_tiles_too_large_names_the_pdk_limit(monkeypatch, tmp_path):
    import chiplab.hw.pdk as pdkmod
    monkeypatch.setattr(pdkmod, "map_to_process", lambda *a, **k: {"area_um2": 5e6})
    (tmp_path / "a.v").write_text("module top; endmodule\n")
    assert tt.pick_tiles([tmp_path / "a.v"], "top", tmp_path / "w", "gf180mcuD")["error"] == "larger than 4x8 tiles"
    assert tt.pick_tiles([tmp_path / "a.v"], "top", tmp_path / "w", "sky130A")["error"] == "larger than 8x2 tiles"


def test_tt_package_rejects_a_shape_the_pdk_does_not_have(monkeypatch, tmp_path):
    monkeypatch.setattr(tt, "ensure_tt_assets", lambda: None)
    with pytest.raises(ValueError, match="gf180mcuD"):
        tt.tt_package([tmp_path / "a.v"], "top", tmp_path, {}, tiles="8x2", pdk="gf180mcuD")


# ------------------------------------------------------------------------------------------- routes

def test_routes_mark_every_figure_vendor_or_unverified():
    assert cost.CHECKED == "2026-11-22"
    for r in ROUTES:
        assert r["provenance"], r["id"]
        for field, src in r["provenance"].items():
            assert src.startswith(("vendor page", "unverified", "tt-support-tools")), (r["id"], field, src)
    ids = {r["id"] for r in ROUTES}
    assert {"tt_sky130", "tt_gf180", "tt_ihp", "waferspace_gf180", "chipfoundry_chipignite", "europractice_gf180",
            "europractice_ihp_sg13g2", "europractice_ihp_sg13cmos"} <= ids


def test_waferspace_slot_fit_check():
    assert waferspace_slot(None) == {"fits": None, "slot": None}
    assert waferspace_slot(0.5)["slot"] == "0.5x0.5"                       # 0.83 mm2 needed in 1.73 mm2 core
    assert waferspace_slot(2.0)["slot"] == "1x0.5"                         # half slot with the larger core
    assert waferspace_slot(3.5)["slot"] == "1x1"                           # 5.83 mm2: more than any half core
    big = waferspace_slot(12.92 * 0.6 + 0.01)
    assert big["fits"] is False and big["slot"] is None
    assert waferspace_slot(12.92 * 0.6 + 0.01, pad_ring=False)["slot"] == "1x1"   # no pad ring: 19.65 mm2 usable
    assert [s["price"] for s in WAFERSPACE_SLOTS] == sorted(s["price"] for s in WAFERSPACE_SLOTS)


def test_estimate_waferspace_uses_gf180_area_and_can_refuse():
    small = _route(estimate(area_by_pdk={"gf180": 400_000.0}), "waferspace_gf180")
    assert small["fits"] is True and small["slot"] == "0.5x0.5" and small["cost"] == 3000.0
    assert small["cost_per_die"] == 3.0 and small["cob_addon"] == 1500.0
    huge = _route(estimate(area_by_pdk={"gf180": 9e6}), "waferspace_gf180")
    assert huge["fits"] is False and huge["cost"] is None
    unknown = _route(estimate(), "waferspace_gf180")
    assert unknown["fits"] is None and unknown["cost"] == 3000.0
    # no GF180 mapping: the sky130 area is scaled by NAND2 size (10.976 / 3.7536)
    scaled = _route(estimate(area_um2=1_000_000.0), "waferspace_gf180")
    assert scaled["fits"] is True and scaled["slot"] == "1x0.5"          # 2.92 mm2 -> 4.87 needed


def test_estimate_tt_tiles_per_pdk():
    r = estimate(area_um2=30_000.0, area_by_pdk={"gf180": 60_000.0})
    sky, gf = _route(r, "tt_sky130"), _route(r, "tt_gf180")
    assert sky["tiles"] == tt_tiles_for(30_000.0, "sky130A") == 3
    assert gf["tiles"] == tt_tiles_for(60_000.0, "gf180mcuD") == 2
    assert sky["cost"] == 3 * 70 + 300
    assert sky["basis"] == "tiles estimated from sky130 synthesis area at 60% utilisation"   # wording kept
    ihp = _route(r, "tt_ihp")
    assert ihp["tiles"] >= 1 and ihp["cost"] is None and "price not known" in ihp["basis"]
    # a GF180 design of 0.5 mm2 fits a TT GF180 shuttle (old code compared it with sky130 tiles)
    assert _route(estimate(area_by_pdk={"gf180": 500_000.0}), "tt_gf180")["fits"] is True
    assert _route(estimate(area_by_pdk={"gf180": 5e6}), "tt_gf180")["fits"] is False


def test_package_tiles_apply_only_to_their_pdk():
    r = estimate(area_um2=30_000.0, tt_tiles=4, tt_pdk="gf180mcuD")
    assert _route(r, "tt_gf180")["tiles"] == 4
    assert _route(r, "tt_sky130")["tiles"] == 3
    legacy = estimate(area_um2=30_000.0, tt_tiles=4)                  # old call: package was sky130
    assert _route(legacy, "tt_sky130")["tiles"] == 4
    assert _route(legacy, "tt_sky130")["basis"] == "tiles from the Tiny Tapeout package"


def test_other_routes_fit_and_price():
    r = estimate(area_um2=100_000.0, area_by_pdk={"gf180": 300_000.0, "ihp": 200_000.0})
    cf = _route(r, "chipfoundry_chipignite")
    assert cf["fits"] is True and cf["cost"] == 14950.0
    assert _route(estimate(area_um2=10e6), "chipfoundry_chipignite")["fits"] is False
    ep = _route(r, "europractice_gf180")
    assert ep["area_mm2_assumed"] == 6.0 and ep["cost"] == round(6.0 * 913)
    ihp = _route(r, "europractice_ihp_sg13g2")
    assert ihp["area_mm2_assumed"] == 0.8 and ihp["cost"] == round(0.8 * 7300)            # 0.33 mm2 core, 0.8 minimum
    big = _route(estimate(area_by_pdk={"ihp": 1_200_000.0}), "europractice_ihp_sg13cmos")
    assert big["area_mm2_assumed"] == 2.0 and big["cost"] == 9000
    for e in r["routes"]:   # every row the chip report renders
        assert {"name", "fits", "cost", "currency", "deadline", "basis", "provenance", "checked"} <= set(e)
