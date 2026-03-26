"""
Notes MCP Server — A lightweight note-taking MCP server backed by local markdown files.

Stores notes as individual .md files in a configurable folder.
Each note has a title (filename), body (file content), and optional tags (YAML front-matter).

Usage:
    python server.py [--notes-dir PATH]

Default notes directory: ./notes (relative to this script)
"""

from __future__ import annotations

import argparse
import datetime
import re
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_NOTES_DIR = _SCRIPT_DIR / "notes"

# ---------------------------------------------------------------------------
# Core logic (pure functions operating on a notes directory)
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Convert a title into a safe, lowercase, dash-separated filename slug."""
    return _SLUG_RE.sub("-", title.strip().lower()).strip("-")[:120]


def note_path(notes_dir: Path, title: str) -> Path:
    """Return the filesystem path for a note given its title."""
    return notes_dir / f"{slugify(title)}.md"


def read_note(path: Path) -> dict:
    """Read a note file and return structured data."""
    text = path.read_text(encoding="utf-8")
    tags: list[str] = []
    body = text

    # Parse YAML-style front-matter for tags
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            front_matter = parts[1]
            body = parts[2].strip()
            for line in front_matter.splitlines():
                if line.strip().startswith("tags:"):
                    raw = line.split(":", 1)[1].strip()
                    tags = [
                        t.strip().strip('"').strip("'")
                        for t in raw.strip("[]").split(",")
                        if t.strip()
                    ]

    stat = path.stat()
    return {
        "title": path.stem.replace("-", " ").title(),
        "slug": path.stem,
        "body": body,
        "tags": tags,
        "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "path": str(path),
    }


def write_note(path: Path, body: str, tags: list[str] | None = None) -> None:
    """Write a note with optional YAML front-matter for tags."""
    content = ""
    if tags:
        tag_str = ", ".join(f'"{t}"' for t in tags)
        content = f"---\ntags: [{tag_str}]\n---\n\n"
    content += body
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# MCP tool implementations (thin wrappers that use a shared NOTES_DIR)
# ---------------------------------------------------------------------------

# NOTES_DIR is set at startup; tests can override via _set_notes_dir().
NOTES_DIR: Path = _DEFAULT_NOTES_DIR


def _set_notes_dir(path: Path) -> None:
    """Override the notes directory (used by tests and CLI arg parsing)."""
    global NOTES_DIR  # noqa: PLW0603
    NOTES_DIR = path
    NOTES_DIR.mkdir(parents=True, exist_ok=True)


def create_note_impl(title: str, body: str, tags: str = "") -> str:
    """Create a new note."""
    path = note_path(NOTES_DIR, title)
    if path.exists():
        return f"Error: A note with slug '{path.stem}' already exists. Use update_note to modify it."
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    write_note(path, body, tag_list)
    return f"Note '{title}' created at {path}"


def read_note_impl(title: str) -> str:
    """Read a note by title."""
    path = note_path(NOTES_DIR, title)
    if not path.exists():
        return f"Error: Note '{title}' not found."
    data = read_note(path)
    result = f"# {data['title']}\n"
    if data["tags"]:
        result += f"Tags: {', '.join(data['tags'])}\n"
    result += f"Modified: {data['modified']}\n\n"
    result += data["body"]
    return result


def update_note_impl(title: str, body: str, tags: str = "") -> str:
    """Update an existing note (replaces content)."""
    path = note_path(NOTES_DIR, title)
    if not path.exists():
        return f"Error: Note '{title}' not found. Use create_note to create it."
    existing = read_note(path)
    tag_list = (
        [t.strip() for t in tags.split(",") if t.strip()] if tags else existing["tags"]
    )
    write_note(path, body, tag_list)
    return f"Note '{title}' updated."


def append_to_note_impl(title: str, content: str) -> str:
    """Append content to an existing note without replacing it."""
    path = note_path(NOTES_DIR, title)
    if not path.exists():
        return f"Error: Note '{title}' not found."
    existing = read_note(path)
    new_body = existing["body"] + "\n\n" + content
    write_note(path, new_body, existing["tags"])
    return f"Content appended to note '{title}'."


def delete_note_impl(title: str) -> str:
    """Delete a note by title."""
    path = note_path(NOTES_DIR, title)
    if not path.exists():
        return f"Error: Note '{title}' not found."
    path.unlink()
    return f"Note '{title}' deleted."


def list_notes_impl(tag: str = "") -> str:
    """List all notes, optionally filtered by tag."""
    notes = []
    for f in sorted(NOTES_DIR.glob("*.md")):
        data = read_note(f)
        if tag and tag.lower() not in [t.lower() for t in data["tags"]]:
            continue
        notes.append(data)

    if not notes:
        return "No notes found." + (f" (filtered by tag: {tag})" if tag else "")

    lines = [f"Found {len(notes)} note(s):\n"]
    for n in notes:
        tags_str = f" [{', '.join(n['tags'])}]" if n["tags"] else ""
        lines.append(
            f"  - **{n['title']}**{tags_str}  (modified: {n['modified'][:10]})"
        )
    return "\n".join(lines)


def search_notes_impl(query: str) -> str:
    """Full-text search across all notes (case-insensitive)."""
    query_lower = query.lower()
    results = []
    for f in sorted(NOTES_DIR.glob("*.md")):
        data = read_note(f)
        if query_lower in data["title"].lower() or query_lower in data["body"].lower():
            idx = data["body"].lower().find(query_lower)
            snippet = ""
            if idx >= 0:
                start = max(0, idx - 40)
                end = min(len(data["body"]), idx + len(query) + 40)
                snippet = "..." + data["body"][start:end].replace("\n", " ") + "..."
            results.append((data, snippet))

    if not results:
        return f"No notes matching '{query}'."

    lines = [f"Found {len(results)} note(s) matching '{query}':\n"]
    for data, snippet in results:
        lines.append(f"  - **{data['title']}**: {snippet}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP Server (only constructed when running as main or explicitly requested)
# ---------------------------------------------------------------------------


def build_mcp_server():
    """Construct the FastMCP server with all tools registered."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "notes",
        instructions=(
            "A lightweight note-taking server. "
            "Create, read, update, delete, list, and search markdown notes."
        ),
    )

    @mcp.tool()
    def create_note(title: str, body: str, tags: str = "") -> str:  # noqa: F811
        """Create a new note.

        Args:
            title: The note title (used as filename).
            body: The note content in markdown.
            tags: Optional comma-separated tags (e.g. "work, idea, urgent").
        """
        return create_note_impl(title, body, tags)

    @mcp.tool()
    def read_note(title: str) -> str:  # noqa: F811
        """Read a note by title.

        Args:
            title: The note title (or slug) to read.
        """
        return read_note_impl(title)

    @mcp.tool()
    def update_note(title: str, body: str, tags: str = "") -> str:  # noqa: F811
        """Update an existing note (replaces content).

        Args:
            title: The note title (or slug) to update.
            body: The new note content in markdown.
            tags: Optional comma-separated tags. Pass empty string to keep existing tags.
        """
        return update_note_impl(title, body, tags)

    @mcp.tool()
    def append_to_note(title: str, content: str) -> str:  # noqa: F811
        """Append content to an existing note without replacing it.

        Args:
            title: The note title (or slug) to append to.
            content: The content to append.
        """
        return append_to_note_impl(title, content)

    @mcp.tool()
    def delete_note(title: str) -> str:  # noqa: F811
        """Delete a note by title.

        Args:
            title: The note title (or slug) to delete.
        """
        return delete_note_impl(title)

    @mcp.tool()
    def list_notes(tag: str = "") -> str:  # noqa: F811
        """List all notes, optionally filtered by tag.

        Args:
            tag: Optional tag to filter by. Leave empty for all notes.
        """
        return list_notes_impl(tag)

    @mcp.tool()
    def search_notes(query: str) -> str:  # noqa: F811
        """Full-text search across all notes (case-insensitive).

        Args:
            query: The search term to look for in note titles and bodies.
        """
        return search_notes_impl(query)

    return mcp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Notes MCP Server")
    parser.add_argument(
        "--notes-dir",
        type=str,
        default=str(_DEFAULT_NOTES_DIR),
        help="Directory where notes are stored as .md files",
    )
    args = parser.parse_args()
    _set_notes_dir(Path(args.notes_dir).resolve())

    mcp = build_mcp_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
