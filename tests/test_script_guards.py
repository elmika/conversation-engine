"""Tests for the input guards in scripts/ that SonarCloud flagged (path traversal, SSRF).

scripts/ isn't a package: import its modules by putting the directory on sys.path, the same way
the scripts import each other. Both modules are stdlib-only, so this pulls in nothing else.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from apply_model_preset import _file_in  # noqa: E402
from session_test_utils import check_http_url  # noqa: E402


def test_file_in_accepts_slug(tmp_path: Path) -> None:
    assert (
        _file_in(tmp_path, "course-session-core", ".md")
        == (tmp_path / "course-session-core.md").resolve()
    )


@pytest.mark.parametrize(
    "name",
    ["../app/main", "../../etc/passwd", "sub/dir", "/etc/passwd", "..", ".hidden", "Upper", ""],
)
def test_file_in_refuses_names_that_are_not_slugs(tmp_path: Path, name: str) -> None:
    with pytest.raises(SystemExit):
        _file_in(tmp_path, name, ".md")


@pytest.mark.parametrize("url", ["http://localhost:8000/healthz", "https://example.com/x"])
def test_check_http_url_accepts_http_and_https(url: str) -> None:
    check_http_url(url)


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://example.com/x", "localhost:8000/healthz", ""]
)
def test_check_http_url_refuses_other_schemes(url: str) -> None:
    with pytest.raises(ValueError):
        check_http_url(url)
