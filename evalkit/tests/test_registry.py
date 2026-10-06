import pytest

from evalkit.core.registry import Registry


class _Foo:
    pass


def test_resolve_builtin():
    reg = Registry()
    reg.register_evaluator("foo", _Foo)
    assert reg.resolve_evaluator("foo") is _Foo


def test_resolve_dotted_path():
    reg = Registry()
    from evalkit.evaluators.generic import GenericEvaluator

    resolved = reg.resolve_evaluator("evalkit.evaluators.generic:GenericEvaluator")
    assert resolved is GenericEvaluator


def test_unknown_name_raises_helpful_error():
    reg = Registry()
    with pytest.raises(KeyError, match="dotted path"):
        reg.resolve_evaluator("nonsense")


def test_bad_dotted_path_module_raises_import_error():
    reg = Registry()
    with pytest.raises(ImportError):
        reg.resolve_evaluator("nonexistent.module:Whatever")


def test_metric_decorator_registers_function():
    reg = Registry()

    @reg.metric("exact_match")
    def exact_match(output: str, reference: str) -> float:
        return 1.0 if output == reference else 0.0

    assert reg.get_metric("exact_match") is exact_match


def test_resolve_dotted_path_with_wrong_class_name_raises_attribute_error():
    reg = Registry()
    with pytest.raises(AttributeError, match="has no attribute"):
        reg.resolve_evaluator("evalkit.evaluators.generic:NoSuchClass")


def test_resolve_reporter_builtin():
    from evalkit.core.report import HTMLReporter

    reg = Registry()
    reg.register_reporter("html", HTMLReporter)
    assert reg.resolve_reporter("html") is HTMLReporter
