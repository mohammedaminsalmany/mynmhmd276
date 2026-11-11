"""Compatibility shim so ``pip install .`` works with older tooling.

All package metadata lives in ``pyproject.toml``; setuptools reads it from
there. This file exists for tools and workflows that still expect a
``setup.py`` entry point.
"""

from setuptools import setup

setup()
