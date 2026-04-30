"""Tests for `dotfiles_setup.mise_snapshot`."""

from __future__ import annotations

import json

from dotfiles_setup.mise_snapshot import (
    SCHEMA_VERSION,
    filter_conda_resolved,
    format_snapshot,
    parse_snapshot,
)


def test_filter_keeps_only_conda_entries() -> None:
    raw = {
        "python": [{"version": "3.14.4"}],
        "conda:cmake": [{"version": "4.3.2"}],
        "conda:ninja": [{"version": "1.13.2"}],
        "node": [{"version": "25.9.0"}],
    }
    assert filter_conda_resolved(raw) == {
        "conda:cmake": "4.3.2",
        "conda:ninja": "1.13.2",
    }


def test_filter_sorts_by_key() -> None:
    raw = {
        "conda:llvm": [{"version": "22.1.4"}],
        "conda:cmake": [{"version": "4.3.2"}],
        "conda:clang": [{"version": "22.1.4"}],
    }
    assert list(filter_conda_resolved(raw).keys()) == [
        "conda:clang",
        "conda:cmake",
        "conda:llvm",
    ]


def test_filter_skips_empty_entries() -> None:
    raw = {
        "conda:cmake": [{"version": "4.3.2"}],
        "conda:phantom": [],
        "conda:no_version": [{}],
    }
    assert filter_conda_resolved(raw) == {"conda:cmake": "4.3.2"}


def test_format_snapshot_is_deterministic() -> None:
    resolved = {"conda:cmake": "4.3.2", "conda:ninja": "1.13.2"}
    text = format_snapshot(resolved)
    parsed = json.loads(text)
    assert parsed["schema_version"] == SCHEMA_VERSION
    assert parsed["tools"] == resolved
    assert text.endswith("\n")
    assert format_snapshot(resolved) == text


def test_parse_snapshot_roundtrip() -> None:
    resolved = {"conda:cmake": "4.3.2", "conda:ninja": "1.13.2"}
    text = format_snapshot(resolved)
    assert parse_snapshot(text) == resolved


def test_parse_snapshot_rejects_invalid_tools_field() -> None:
    bad = json.dumps({"schema_version": 1, "tools": "not a dict"})
    try:
        parse_snapshot(bad)
    except TypeError:
        return
    msg = "expected TypeError for non-dict tools field"
    raise AssertionError(msg)
