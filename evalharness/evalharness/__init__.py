"""Forwarding shim for evalkit backward compatibility."""
import evalkit
from evalkit import registry
from evalkit import __version__

__all__ = ["registry", "__version__"]
