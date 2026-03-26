"""
Notes MCP Server — A lightweight note-taking MCP server backed by local markdown files.

Stores notes as individual .md files in a configurable folder.
Each note has a title (filename), body (file content), and optional tags (YAML front-matter).

Usage:
    python server.py [--notes-dir PATH]

Default notes directory: ./notes (relative to this script)
"""

import argparse
import datetime
import os
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_NOTES_DIR = _SCRIPT_DIR / "notes"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Notes MCP Server")
    parser.add_argument(
        "--notes-dir",
        type=str,
        default=str(_DEFAULT_NOTES_DIR),
        help="Directory where notes are stored as .md files",
    )
    return parser.parse_args()


_args = _parse_args()
NOTES_DIR = Path(_args.notes_dir).resolve()
NOTES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(title: str) -> str:
    """Convert a title into a safe, lowercase, dash-separated filename slug."""
    return _SLUG_RE.sub("-", title.strip().lower()).strip("-")[:120]


def _note_path(title: str) -> Path:
    return NOTES_DIR / f"{_slugify(title)}.md"


def _read_note(path: Path) -> dict:
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
                    tags = [t.strip().strip('"').strip("'") for t in raw.strip("[]").split(",") if t.strip()]

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


def _write_note(path: Path, body: str, tags: list[str] | None = None) -> None:
    """Write a note with optional YAML front-matter for tags."""
    content = ""
    if tags:
        tag_str = ", ".join(f'"{t}"' for t in tags)
        content = f"---\ntags: [{tag_str}]\n---\n\n"
    content += body
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "notes",
    instructions="A lightweight note-taking server. Create, read, update, delete, list, and search markdown notes.",
)


@mcp.tool()
def create_note(title: str, body: str, tags: str = "") -> str:
    """Create a new note.

    Args:
        title: The note title (used as filename).
        body: The note content in markdown.
        tags: Optional comma-separated tags (e.g. "work, idea, urgent").
    """
    path = _note_path(title)
    if path.exists():
        return f"Error: A note with slug '{path.stem}' already exists. Use update_note to modify it."

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    _write_note(path, body, tag_list)
    return f"Note '{title}' created at {path}"


@mcp.tool()
def read_note(title: str) -> str:
    """Read a note by title.

    Args:
        title: The note title (or slug) to read.
    """
    path = _note_path(title)
    if not path.exists():
        return f"Error: Note '{title}' not found."
    note = _read_note(path)
    result = f"# {note['title']}\n"
    if note["tags"]:
        result += f"Tags: {', '.join(note['tags'])}\n"
    result += f"Modified: {note['modified']}\n\n"
    result += note["body"]
    return result


@mcp.tool()
def update_note(title: str, body: str, tags: str = "") -> str:
    """Update an existing note (replaces content).

    Args:
        title: The note title (or slug) to update.
        body: The new note content in markdown.
        tags: Optional comma-separated tags. Pass empty string to keep existing tags.
    """
    path = _note_path(title)
    if not path.exists():
        return f"Error: Note '{title}' not found. Use create_note to create it."

    existing = _read_note(path)
    tag_list = (
        [t.strip() for t in tags.split(",") if t.strip()]
        if tags
        else existing["tags"]
    )
    _write_note(path, body, tag_list)
    return f"Note '{title}' updated."


@mcp.tool()
def append_to_note(title: str, content: str) -> str:
    """Append content to an existing note without replacing it.

    Args:
        title: The note title (or slug) to append to.
        content: The content to append.
    """
    path = _note_path(title)
    if not path.exists():
        return f"Error: Note '{title}' not found."

    existing = _read_note(path)
    new_body = existing["body"] + "\n\n" + content
    _write_note(path, new_body, existing["tags"])
    return f"Content appended to note '{title}'."


@mcp.tool()
def delete_note(title: str) -> str:
    """Delete a note by title.

    Args:
        title: The note title (or slug) to delete.
    """
    path = _note_path(title)
    if not path.exists():
        return f"Error: Note '{title}' not found."
    path.unlink()
    return f"Note '{title}' deleted."


@mcp.tool()
def list_notes(tag: str = "") -> str:
    """List all notes, optionally filtered by tag.

    Args:
        tag: Optional tag to filter by. Leave empty for all notes.
    """
    notes = []
    for f in sorted(NOTES_DIR.glob("*.md")):
        note = _read_note(f)
        if tag and tag.lower() not in [t.lower() for t in note["tags"]]:
            continue
        notes.append(note)

    if not notes:
        return "No notes found." + (f" (filtered by tag: {tag})" if tag else "")

    lines = [f"Found {len(notes)} note(s):\n"]
    for n in notes:
        tags_str = f" [{', '.join(n['tags'])}]" if n["tags"] else ""
        lines.append(f"  - **{n['title']}**{tags_str}  (modified: {n['modified'][:10]})")
    return "\n".join(lines)


@mcp.tool()
def search_notes(query: str) -> str:
    """Full-text search across all notes (case-insensitive).

    Args:
        query: The search term to look for in note titles and bodies.
    """
    query_lower = query.lower()
    results = []
    for f in sorted(NOTES_DIR.glob("*.md")):
        note = _read_note(f)
        if query_lower in note["title"].lower() or query_lower in note["body"].lower():
            # Find a snippet around the match
            idx = note["body"].lower().find(query_lower)
            snippet = ""
            if idx >= 0:
                start = max(0, idx - 40)
                end = min(len(note["body"]), idx + len(query) + 40)
                snippet = "..." + note["body"][start:end].replace("\n", " ") + "..."
            results.append((note, snippet))

    if not results:
        return f"No notes matching '{query}'."

    lines = [f"Found {len(results)} note(s) matching '{query}':\n"]
    for note, snippet in results:
        lines.append(f"  - **{note['title']}**: {snippet}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
