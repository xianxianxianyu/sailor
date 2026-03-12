"""Artifact Module

Unified artifact storage for all Follow system outputs.
"""
from .models import Artifact
from .repository import ArtifactRepository

__all__ = ["Artifact", "ArtifactRepository"]
