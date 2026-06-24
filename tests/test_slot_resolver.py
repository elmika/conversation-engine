"""Unit tests for FileSlotResolver (Layer 1b file-based slot resolver)."""

from app.infra.slot_resolver_files import FileSlotResolver


def test_resolve_returns_content(tmp_path) -> None:
    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "u1.md").write_text("# Profile", encoding="utf-8")
    resolver = FileSlotResolver(str(tmp_path), "u1")
    assert resolver.resolve("user") == "# Profile"


def test_resolve_missing_returns_none(tmp_path) -> None:
    resolver = FileSlotResolver(str(tmp_path), "u1")
    assert resolver.resolve("user") is None


def test_exists_true_when_file_present(tmp_path) -> None:
    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "u1.md").write_text("# Profile", encoding="utf-8")
    resolver = FileSlotResolver(str(tmp_path), "u1")
    assert resolver.exists("user") is True


def test_exists_false_when_file_absent(tmp_path) -> None:
    resolver = FileSlotResolver(str(tmp_path), "u1")
    assert resolver.exists("user") is False


def test_exists_does_not_read_content(tmp_path, monkeypatch) -> None:
    """exists() must check presence only — never read the file body."""
    from pathlib import Path

    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "u1.md").write_text("# Profile", encoding="utf-8")

    def _boom(*args, **kwargs):
        raise AssertionError("exists() must not read file content")

    monkeypatch.setattr(Path, "read_text", _boom)
    resolver = FileSlotResolver(str(tmp_path), "u1")
    assert resolver.exists("user") is True
