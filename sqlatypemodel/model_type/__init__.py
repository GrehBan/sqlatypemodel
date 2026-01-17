"""SQLAlchemy TypeDecorator for Pydantic model serialization.

This module provides ModelType for storing and tracking Pydantic,
Dataclass, and Attrs models in database JSON columns.
"""

from __future__ import annotations

from .model_type import ModelType

__all__ = ("ModelType",)
