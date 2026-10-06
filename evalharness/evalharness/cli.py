"""Forwarding shim for evalkit backward compatibility."""
from evalkit.cli import *  # noqa: F401, F403

if __name__ == "__main__":
    main()
