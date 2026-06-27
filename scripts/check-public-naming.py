"""Check public-facing Delegator naming.

Fails if old public-facing phrases remain in Markdown files,
but allows `agent-file-coordination/*` schema namespace occurrences.

Standard library only, Python 3.8+.
"""
import pathlib
import sys

FORBIDDEN_PUBLIC_PHRASES = [
    "agent-file-coordination skill",
    "the agent-file-coordination skill",
    "use the agent-file-coordination skill",
    "install the full agent-file-coordination skill",
]

EXCLUDE_PARTS = {".git", ".venv", "node_modules", "private-notes", ".learnings", ".codebuddy", ".agent-inbox", "建议"}


def main() -> int:
    root = pathlib.Path(".")
    errors: list[str] = []

    for p in sorted(root.rglob("*.md")):
        if any(part in EXCLUDE_PARTS for part in p.parts):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()

        for phrase in FORBIDDEN_PUBLIC_PHRASES:
            if phrase in lowered:
                errors.append(f"{p}: public-facing old name remains: {phrase}")

    if errors:
        print("\n".join(errors))
        return 1

    print("PASS: no forbidden public-facing old-name phrases found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
