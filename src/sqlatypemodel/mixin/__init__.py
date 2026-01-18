"""Mixin classes for automatic mutation tracking in database models.

This module provides MutableMixin and LazyMutableMixin for tracking
changes to nested Python objects stored in SQLAlchemy JSON columns.
"""

from __future__ import annotations

from .mixin import BaseMutableMixin, LazyMutableMixin, MutableMixin

__all__ = ("MutableMixin", "LazyMutableMixin", "BaseMutableMixin")
