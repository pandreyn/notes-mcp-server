"""Tests for the notes MCP server core logic and tool implementations."""

from __future__ import annotations

from pathlib import Path

import pytest

import server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def notes_dir(tmp_path: Path):
    """Point every test at an isolated temporary notes directory."""
    server._set_notes_dir(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic_title(self):
        assert server.slugify("My First Note") == "my-first-note"

    def test_special_characters(self):
        assert server.slugify("Hello, World! #2") == "hello-world-2"

    def test_leading_trailing_whitespace(self):
        assert server.slugify("  padded title  ") == "padded-title"

    def test_truncates_at_120(self):
        long_title = "a" * 200
        assert len(server.slugify(long_title)) <= 120

    def test_empty_string(self):
        assert server.slugify("") == ""

    def test_only_special_chars(self):
        assert server.slugify("!!!???") == ""


# ---------------------------------------------------------------------------
# note_path
# ---------------------------------------------------------------------------


class TestNotePath:
    def test_returns_md_file(self, notes_dir: Path):
        path = server.note_path(notes_dir, "My Note")
        assert path.suffix == ".md"
        assert path.parent == notes_dir

    def test_slug_in_filename(self, notes_dir: Path):
        path = server.note_path(notes_dir, "Hello World")
        assert path.name == "hello-world.md"


# ---------------------------------------------------------------------------
# write_note / read_note (core helpers)
# ---------------------------------------------------------------------------


class TestWriteAndReadNote:
    def test_write_and_read_plain(self, notes_dir: Path):
        path = notes_dir / "test.md"
        server.write_note(path, "Hello body")
        data = server.read_note(path)
        assert data["body"] == "Hello body"
        assert data["tags"] == []

    def test_write_and_read_with_tags(self, notes_dir: Path):
        path = notes_dir / "tagged.md"
        server.write_note(path, "Tagged body", ["work", "urgent"])
        data = server.read_note(path)
        assert data["body"] == "Tagged body"
        assert data["tags"] == ["work", "urgent"]

    def test_read_returns_metadata(self, notes_dir: Path):
        path = notes_dir / "meta.md"
        server.write_note(path, "content")
        data = server.read_note(path)
        assert "title" in data
        assert "slug" in data
        assert "created" in data
        assert "modified" in data
        assert "path" in data

    def test_write_no_tags_gives_no_frontmatter(self, notes_dir: Path):
        path = notes_dir / "plain.md"
        server.write_note(path, "no tags")
        raw = path.read_text(encoding="utf-8")
        assert not raw.startswith("---")

    def test_write_empty_tag_list_gives_no_frontmatter(self, notes_dir: Path):
        path = notes_dir / "empty-tags.md"
        server.write_note(path, "body", [])
        raw = path.read_text(encoding="utf-8")
        assert not raw.startswith("---")


# ---------------------------------------------------------------------------
# create_note
# ---------------------------------------------------------------------------


class TestCreateNote:
    def test_creates_file(self, notes_dir: Path):
        result = server.create_note_impl("Meeting Notes", "Discuss roadmap")
        assert "created" in result.lower()
        assert (notes_dir / "meeting-notes.md").exists()

    def test_creates_with_tags(self, notes_dir: Path):
        server.create_note_impl("Tagged", "body", "work, urgent")
        data = server.read_note(notes_dir / "tagged.md")
        assert data["tags"] == ["work", "urgent"]

    def test_duplicate_returns_error(self, notes_dir: Path):
        server.create_note_impl("Dup", "first")
        result = server.create_note_impl("Dup", "second")
        assert "error" in result.lower()

    def test_empty_tags_string(self, notes_dir: Path):
        server.create_note_impl("No Tags", "body", "")
        data = server.read_note(notes_dir / "no-tags.md")
        assert data["tags"] == []


# ---------------------------------------------------------------------------
# read_note
# ---------------------------------------------------------------------------


class TestReadNote:
    def test_read_existing(self, notes_dir: Path):
        server.create_note_impl("Readable", "Some content")
        result = server.read_note_impl("Readable")
        assert "Some content" in result
        assert "# Readable" in result

    def test_read_nonexistent(self):
        result = server.read_note_impl("Ghost")
        assert "error" in result.lower()

    def test_read_shows_tags(self, notes_dir: Path):
        server.create_note_impl("With Tags", "body", "alpha, beta")
        result = server.read_note_impl("With Tags")
        assert "alpha" in result
        assert "beta" in result


# ---------------------------------------------------------------------------
# update_note
# ---------------------------------------------------------------------------


class TestUpdateNote:
    def test_update_body(self, notes_dir: Path):
        server.create_note_impl("Updatable", "old body")
        result = server.update_note_impl("Updatable", "new body")
        assert "updated" in result.lower()
        data = server.read_note(notes_dir / "updatable.md")
        assert data["body"] == "new body"

    def test_update_preserves_tags_when_empty(self, notes_dir: Path):
        server.create_note_impl("Keep Tags", "body", "important")
        server.update_note_impl("Keep Tags", "new body", "")
        data = server.read_note(notes_dir / "keep-tags.md")
        assert "important" in data["tags"]

    def test_update_replaces_tags(self, notes_dir: Path):
        server.create_note_impl("Replace Tags", "body", "old")
        server.update_note_impl("Replace Tags", "body", "new")
        data = server.read_note(notes_dir / "replace-tags.md")
        assert data["tags"] == ["new"]

    def test_update_nonexistent(self):
        result = server.update_note_impl("Missing", "body")
        assert "error" in result.lower()


# ---------------------------------------------------------------------------
# append_to_note
# ---------------------------------------------------------------------------


class TestAppendToNote:
    def test_append(self, notes_dir: Path):
        server.create_note_impl("Appendable", "line one")
        result = server.append_to_note_impl("Appendable", "line two")
        assert "appended" in result.lower()
        data = server.read_note(notes_dir / "appendable.md")
        assert "line one" in data["body"]
        assert "line two" in data["body"]

    def test_append_preserves_tags(self, notes_dir: Path):
        server.create_note_impl("Tagged Append", "start", "keep-me")
        server.append_to_note_impl("Tagged Append", "extra")
        data = server.read_note(notes_dir / "tagged-append.md")
        assert "keep-me" in data["tags"]

    def test_append_nonexistent(self):
        result = server.append_to_note_impl("Nope", "text")
        assert "error" in result.lower()


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------


class TestDeleteNote:
    def test_delete_existing(self, notes_dir: Path):
        server.create_note_impl("Deletable", "bye")
        result = server.delete_note_impl("Deletable")
        assert "deleted" in result.lower()
        assert not (notes_dir / "deletable.md").exists()

    def test_delete_nonexistent(self):
        result = server.delete_note_impl("Ghost")
        assert "error" in result.lower()


# ---------------------------------------------------------------------------
# list_notes
# ---------------------------------------------------------------------------


class TestListNotes:
    def test_empty_directory(self):
        result = server.list_notes_impl()
        assert "no notes" in result.lower()

    def test_lists_all(self, notes_dir: Path):
        server.create_note_impl("Alpha", "a")
        server.create_note_impl("Beta", "b")
        result = server.list_notes_impl()
        assert "2 note(s)" in result
        assert "Alpha" in result
        assert "Beta" in result

    def test_filter_by_tag(self, notes_dir: Path):
        server.create_note_impl("Work Note", "w", "work")
        server.create_note_impl("Personal Note", "p", "personal")
        result = server.list_notes_impl(tag="work")
        assert "1 note(s)" in result
        assert "Work" in result
        assert "Personal" not in result

    def test_filter_case_insensitive(self, notes_dir: Path):
        server.create_note_impl("CaseTest", "x", "Important")
        result = server.list_notes_impl(tag="important")
        assert "1 note(s)" in result

    def test_filter_no_match(self, notes_dir: Path):
        server.create_note_impl("Something", "x", "alpha")
        result = server.list_notes_impl(tag="nonexistent")
        assert "no notes" in result.lower()


# ---------------------------------------------------------------------------
# search_notes
# ---------------------------------------------------------------------------


class TestSearchNotes:
    def test_search_in_body(self, notes_dir: Path):
        server.create_note_impl("Doc", "The quick brown fox")
        result = server.search_notes_impl("brown fox")
        assert "1 note(s)" in result

    def test_search_in_title(self, notes_dir: Path):
        server.create_note_impl("Architecture Design", "empty")
        result = server.search_notes_impl("architecture")
        assert "1 note(s)" in result

    def test_search_case_insensitive(self, notes_dir: Path):
        server.create_note_impl("Case", "UPPERCASE content")
        result = server.search_notes_impl("uppercase")
        assert "1 note(s)" in result

    def test_search_no_match(self, notes_dir: Path):
        server.create_note_impl("Irrelevant", "nothing here")
        result = server.search_notes_impl("zzzzz")
        assert "no notes" in result.lower()

    def test_search_multiple_matches(self, notes_dir: Path):
        server.create_note_impl("A", "shared keyword")
        server.create_note_impl("B", "also shared keyword")
        result = server.search_notes_impl("shared")
        assert "2 note(s)" in result

    def test_search_returns_snippet(self, notes_dir: Path):
        server.create_note_impl("Snippet", "before the needle after")
        result = server.search_notes_impl("needle")
        assert "needle" in result
        assert "..." in result
