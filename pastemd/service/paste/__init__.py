# -*- coding: utf-8 -*-
"""Paste placers for clipboard-based content placement.

This module provides placers that use clipboard + simulated keystroke paste
as the placement method. This is useful for applications that don't support
direct automation APIs but accept clipboard content via standard paste.
"""

from .base import BasePastePlacer
from .rich_text import RichTextPastePlacer
from .text import PlainTextPastePlacer
from .file import FilePastePlacer

__all__ = [
    "BasePastePlacer",
    "RichTextPastePlacer",
    "PlainTextPastePlacer",
    "FilePastePlacer",
]
