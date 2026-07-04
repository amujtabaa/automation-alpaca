"""AIR-011: resource-leak enforcement must be version-proof.

``pyproject.toml`` promotes a leaked/unclosed ``sqlite3.Connection``'s
``ResourceWarning`` to an error (F-008). But on Python 3.13+ an unraisable
ResourceWarning (raised inside a GC'd object's ``__del__``) is delivered by
pytest's ``unraisableexception`` plugin **wrapped** in
``PytestUnraisableExceptionWarning`` — which is *not* a ``ResourceWarning``
subclass, so the plain ``error::ResourceWarning`` filter alone would let a leaked
connection slip through on newer Pythons. These tests pin that BOTH the plain and
the wrapped forms are promoted to errors by the active configuration, so removing
either filter line fails the suite.
"""

from __future__ import annotations

import warnings

import pytest


def test_plain_resourcewarning_is_promoted_to_error():
    # The active filterwarnings config raises ResourceWarning as an error (F-008).
    with pytest.raises(ResourceWarning):
        warnings.warn("simulated leaked resource", ResourceWarning)


def test_wrapped_unraisable_warning_is_promoted_to_error():
    # AIR-011: the wrapper pytest uses for an unraisable (GC-time) ResourceWarning
    # on Python 3.13+ must ALSO be an error, or a leaked connection escapes there.
    with pytest.raises(pytest.PytestUnraisableExceptionWarning):
        warnings.warn(
            "simulated wrapped unraisable ResourceWarning",
            pytest.PytestUnraisableExceptionWarning,
        )
