# Notes MCP Server

A lightweight [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for managing personal text notes as local markdown files.

## Features

- **7 tools**: `create_note`, `read_note`, `update_note`, `append_to_note`, `delete_note`, `list_notes`, `search_notes`
- Notes stored as individual `.md` files with optional YAML front-matter tags
- Full-text search across all notes
- Tag-based filtering
- Configurable notes directory via `--notes-dir`

## Requirements

- Python 3.11+
- `mcp` Python SDK (`pip install mcp`)

## Quick Start

```bash
pip install mcp
python server.py --notes-dir /path/to/your/notes
```

## VS Code / Copilot Integration

Add to your VS Code **User Settings** (`settings.json`) or workspace `.vscode/mcp.json`:

```json
{
  "mcp": {
    "servers": {
      "notes": {
        "command": "python",
        "args": [
          "/path/to/server.py",
          "--notes-dir",
          "/path/to/your/notes"
        ]
      }
    }
  }
}
```

Then reload VS Code and your AI assistant can manage notes for you:

- *"Create a note called 'standup items' tagged 'daily'"*
- *"Search my notes for 'pipeline'"*
- *"List all notes tagged 'urgent'"*
- *"Append today's progress to my 'sprint log' note"*

## GitHub Copilot CLI (Agency) Integration

Add to your global Agency config at `~/.agency/agency.toml`:

```toml
[mcps.servers.notes]
command = "python /path/to/server.py --notes-dir /path/to/your/notes"
```

Then restart the CLI session. Tools will be available as `notes-create_note`, `notes-read_note`, `notes-search_notes`, etc.

## How Notes Are Stored

Each note is a markdown file named by slugifying the title:

```
notes/
  standup-items.md
  sprint-log.md
  architecture-ideas.md
```

Notes can have optional YAML front-matter for tags:

```markdown
---
tags: ["daily", "work"]
---

Your note content here...
```

## License

MIT
