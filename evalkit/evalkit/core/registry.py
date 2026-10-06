from __future__ import annotations

import importlib
from typing import Callable, Type


class Registry:
    """Central registry for evaluators, adapters, judge backends, and reporters.

    Deliberately NOT entry-points/auto-discovery based. evalkit never imports
    third-party packages on its own — every extension is either a built-in
    registered here at import time, or a dotted path ("your.module:YourClass")
    a user points their own config at. This keeps evalkit from ever being on
    the hook for someone else's plugin code.
    """

    def __init__(self) -> None:
        self._evaluators: dict[str, Type] = {}
        self._adapters: dict[str, Type] = {}
        self._judge_backends: dict[str, Type] = {}
        self._reporters: dict[str, Type] = {}
        self._metrics: dict[str, Callable] = {}

    # -- built-in / programmatic registration --------------------------------

    def register_evaluator(self, name: str, cls: Type) -> None:
        self._evaluators[name] = cls

    def register_adapter(self, name: str, cls: Type) -> None:
        self._adapters[name] = cls

    def register_judge_backend(self, name: str, cls: Type) -> None:
        self._judge_backends[name] = cls

    def register_reporter(self, name: str, cls: Type) -> None:
        self._reporters[name] = cls

    def metric(self, name: str) -> Callable:
        """Decorator to register a bare scoring function without writing a
        full BaseEvaluator subclass: ``@registry.metric("my_metric")``."""

        def wrap(fn: Callable) -> Callable:
            self._metrics[name] = fn
            return fn

        return wrap

    def get_metric(self, name: str) -> Callable:
        return self._metrics[name]

    # -- resolution: built-in name OR dotted path "module.sub:ClassName" ----

    def resolve_evaluator(self, ref: str) -> Type:
        return self._resolve(ref, self._evaluators)

    def resolve_adapter(self, ref: str) -> Type:
        return self._resolve(ref, self._adapters)

    def resolve_judge_backend(self, ref: str) -> Type:
        return self._resolve(ref, self._judge_backends)

    def resolve_reporter(self, ref: str) -> Type:
        return self._resolve(ref, self._reporters)

    def _resolve(self, ref: str, table: dict[str, Type]) -> Type:
        if ref in table:
            return table[ref]
        if ":" in ref:
            module_path, class_name = ref.split(":", 1)
            try:
                module = importlib.import_module(module_path)
            except ImportError as exc:
                raise ImportError(
                    f"Could not import module '{module_path}' referenced by '{ref}'. "
                    "Dotted-path references must be importable from your project "
                    "(e.g. run evalkit from your project root, or install it as a package)."
                ) from exc
            try:
                return getattr(module, class_name)
            except AttributeError as exc:
                raise AttributeError(
                    f"Module '{module_path}' has no attribute '{class_name}' (from '{ref}')."
                ) from exc
        raise KeyError(
            f"'{ref}' is not a built-in and is not a dotted path "
            f"('your.module:YourClassName'). Known built-ins: {sorted(table)}"
        )


# One shared instance — built-ins register themselves here on `import evalkit`.
registry = Registry()
