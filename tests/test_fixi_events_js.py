"""
The shim's contract, pinned without a browser.

fixi-events.js cannot run under pytest, so this pins the strings its behaviour
depends on, in the shim and in the vendored fixi.js it relies on. The optional
tests/test_browser.py runs the real thing under Playwright.
"""

import pathlib

STATIC = pathlib.Path(__file__).resolve().parent.parent / "dj_fixi" / "static" / "dj_fixi"
SHIM = (STATIC / "fixi-events.js").read_text()
FIXI = (STATIC / "fixi.js").read_text()


def test_shim_listens_after_the_swap_not_before():
    assert 'addEventListener("fx:swapped"' in SHIM
    assert '"fx:after"' not in SHIM


def test_shim_dispatches_on_body_when_the_requester_is_gone_and_honours_target():
    assert "document.body" in SHIM
    assert "document.querySelector(detail.target)" in SHIM
    assert "bubbles: true, composed: true" in SHIM
    assert "fired.has(cfg)" in SHIM  # one delivery per request, even from a shadow root


def test_shim_guards_use_fixi_predicates():
    assert 'addEventListener("fx:config"' in SHIM and "cfg.target === elt" in SHIM
    assert "swap in cfg.target" in SHIM and "/(before|after)(begin|end)/.test(swap)" in SHIM
    assert 'addEventListener("fx:error"' in SHIM


def test_fixi_js_lines_the_shim_depends_on():
    """If a fixi.js upgrade changes any of these, the shim needs another look."""
    assert 'send(elt, "swapped", {cfg})' in FIXI
    assert 'if (!document.contains(elt)) send(document, "swapped", {cfg})' in FIXI
    assert 'let go = send(elt, "config", {cfg, requests:reqs})' in FIXI
    assert 'send(elt, "error", {cfg, error})' in FIXI
    assert 'target:document.querySelector(attr(elt, "fx-target")) ?? elt' in FIXI
    assert "else if(cfg.swap in cfg.target)" in FIXI
    assert "else if(cfg.swap !== 'none') throw cfg.swap" in FIXI
