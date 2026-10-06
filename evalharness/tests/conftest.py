import pytest


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Every test runs with CWD set to its own tmp_path. Without this,
    tests that go through Runner with default config (cache=True,
    cache_dir=".evalharness/cache", a relative path) would write cache
    files into whatever the real CWD happens to be — polluting the repo
    directory instead of staying isolated per test. Subprocess-based CLI
    tests inherit this CWD too, since monkeypatch.chdir actually calls
    os.chdir() on the process.
    """
    monkeypatch.chdir(tmp_path)
