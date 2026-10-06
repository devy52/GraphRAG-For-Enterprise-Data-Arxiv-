"""Backward-compatibility wrapper forwarding all APIs to evalkit."""
import evalkit
from evalkit import registry, __version__

__all__ = ["registry", "__version__"]
