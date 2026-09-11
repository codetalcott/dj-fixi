"""
The vocabulary in dj_fixi.attrs is pinned against the vendored fixi.js, so an
upgrade of fixi.js that changes what it reads or how it swaps fails here first.
"""

import pathlib
import re

from dj_fixi import attrs

FIXI = (pathlib.Path(__file__).resolve().parent.parent / "dj_fixi/static/dj_fixi/fixi.js").read_text()


def test_fixi_reads_exactly_the_attributes_we_say_it_does():
    assert set(re.findall(r"fx-[a-z]+", FIXI)) == set(attrs.FX_ATTRIBUTES)


def test_the_lines_each_rule_depends_on():
    assert "let attr = (elt, name, defaultVal)=>elt.getAttribute(name) || defaultVal" in FIXI  # fx-action="" -> undefined
    assert 'method:attr(elt, "fx-method", "GET").toUpperCase()' in FIXI
    assert 'target:document.querySelector(attr(elt, "fx-target")) ?? elt' in FIXI
    assert "/(before|after)(begin|end)/.test(cfg.swap)" in FIXI
    assert "else if(cfg.swap in cfg.target)" in FIXI
    assert "else if(cfg.swap !== 'none') throw cfg.swap" in FIXI
    assert "elt.addEventListener(elt.__fixi.evt, elt.__fixi, options)" in FIXI
    assert 'if (n.matches("[fx-action]")) init(n)' in FIXI
    assert 'send(elt, "error", {cfg, error})' in FIXI


def test_swap_values_cover_every_swap_fixi_performs():
    positions = {"beforebegin", "afterbegin", "beforeend", "afterend"}
    assert positions <= set(attrs.SWAP_VALUES.values())
    for prop in ("innerHTML", "outerHTML", "textContent", "innerText"):
        assert prop in attrs.SWAP_VALUES.values()
