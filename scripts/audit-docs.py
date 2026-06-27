#!/usr/bin/env python3
"""Lightweight documentation audit script for the agent-file-coordination skill.

Python stdlib only. Scans a target directory (default: current directory) for
Markdown files and reports:

  1. Broken intra-repo Markdown links.
     Skips external URLs (http, https, ftp), mailto links, pure anchors, and
     placeholder/template links wrapped in angle brackets (for example
     `<absolute-task-file-path>`).

  2. Terminology inconsistency: camelCase variants of the five canonical
     multi-word terms (`Agent Name`, `Permission Scope`, `Workspace Mode`,
     `Protocol Mode`, `Coordinator Authority`). The kebab-case forms
     (`agent-name`, etc.) and the snake_case YAML keys (`agent_name`, etc.)
     are intentionally NOT flagged to avoid false positives, because
     kebab-case English phrases (for example "agent-name lookup" inside a
     hyphenated phrase) are common in flowing prose and the snake_case keys
     are the canonical YAML field names.

     Task lifecycle states (`DRAFT`, `ASSIGNED`, ...) are checked for value
     correctness by `scripts/validate-agent-inbox.py` already, and lowercase
     prose usage of words like "assigned" or "blocked" is normal English, so
     this script does not re-check lifecycle-state casing in prose.

  3. `schema_version` consistency in Markdown frontmatter and `.jsonl` event
     log records. The expected current value is `0.1.0`.

Exits 0 on success and 1 on any finding, so it is safe to use in CI.

Usage:
    python -B scripts/audit-docs.py [target]
"""

import json
import os
import re
import sys


EXPECTED_SCHEMA_VERSION = "0.1.0"

# Root SKILL.md byte budget, two-tier.
#   SKILL_SIZE_TARGET  soft target. At/below this the gate is clean.
#   SKILL_SIZE_HARD    hard ceiling. Between target and ceiling the gate still
#                      passes but emits an advisory (the tolerance band, so a
#                      small edit no longer forces a byte-shaving commit); above
#                      the ceiling it fails.
# Both values may only ratchet down; raising either requires an explicit
# maintainer acceptance recorded in the PR description.
SKILL_SIZE_TARGET = 8_000
SKILL_SIZE_HARD = 9_000

# Advisory installed-weight growth gate. Counts top-level scripts/*.py and
# references/*.md and warns (never fails, never changes the exit code) when
# either exceeds its budget, so surface-area creep is visible before it
# compounds. Prefer merging a new concept into an existing file; raising a
# threshold should be a conscious, reviewed choice.
SCRIPTS_COUNT_WARN = 40
REFERENCES_COUNT_WARN = 40

SKIP_DIRS = {
    ".git",
    ".learnings",
    ".codebuddy",
    ".idea",
    ".vscode",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "out",
    "target",
    ".cache",
    ".tmp",
    ".nyc_output",
    "coverage",
    "htmlcov",
    "site",
    "_site",
    ".docusaurus",
    ".next",
    ".nuxt",
    ".gradle",
    "vendor",
    ".terraform",
    ".agent-inbox",
    "review_inputs",
}

CANONICAL_MULTIWORD_TERMS = (
    "Agent Name",
    "Permission Scope",
    "Workspace Mode",
    "Protocol Mode",
    "Coordinator Authority",
)


def find_doc_files(target):
    """Yield absolute paths of .md and .jsonl files under target, skipping SKIP_DIRS."""
    if os.path.isfile(target):
        if target.endswith((".md", ".jsonl")):
            yield os.path.abspath(target)
        return

    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f.endswith((".md", ".jsonl")):
                yield os.path.abspath(os.path.join(root, f))


def safe_relpath(path, start=None):
    """Return a relative path, falling back to the absolute path on cross-drive errors."""
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return path


def is_skippable_link_target(target):
    """True for external URLs, mailto, anchors, or placeholder template targets."""
    if not target:
        return True
    lowered = target.strip().lower()
    if lowered.startswith(("http://", "https://", "ftp://", "mailto:", "tel:")):
        return True
    if target.startswith("#"):
        return True
    if target.startswith("<") and target.endswith(">"):
        return True
    return False


def extract_markdown_links(content):
    """Yield (target, line_no) for every Markdown inline link in content.

    Skips image syntax (`![alt](src)`) by requiring no leading `!`.
    """
    pattern = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
    for line_no, line in enumerate(content.splitlines(), 1):
        for match in pattern.finditer(line):
            yield match.group(1).strip(), line_no


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def extract_frontmatter(content):
    """Return (frontmatter_text, body_text). Returns (None, full_content) if absent."""
    lines = content.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None, content
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            end_idx = i
            break
    if end_idx == -1:
        return None, content
    return "\n".join(lines[1:end_idx]), "\n".join(lines[end_idx + 1:])


def build_camelcase_pattern():
    """Return a compiled regex matching camelCase variants of canonical multi-word terms.

    Matches both TitleCase joined forms (`AgentName`, `PermissionScope`) and
    lowerCamelCase forms (`agentName`, `permissionScope`), since both are
    non-canonical for prose documentation. The canonical form for prose is
    the spaced title case (`Agent Name`, `Permission Scope`).
    """
    variants = []
    canonical_map = {}
    for term in CANONICAL_MULTIWORD_TERMS:
        parts = re.split(r"\s+|_", term)
        if len(parts) < 2:
            continue
        title_camel = "".join(p[0].upper() + p[1:] for p in parts)
        lower_camel = parts[0].lower() + "".join(p[0].upper() + p[1:] for p in parts[1:])
        variants.append(title_camel)
        variants.append(lower_camel)
        canonical_map[title_camel] = term
        canonical_map[lower_camel] = term
    escaped = [re.escape(v) for v in variants]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b"), canonical_map


CAMELCASE_RE, CAMELCASE_TO_CANONICAL = build_camelcase_pattern()


def check_links(doc_files, errors):
    """Report broken intra-repo Markdown links."""
    for path in doc_files:
        if not path.endswith(".md"):
            continue
        content = _read_text(path)
        if not content:
            continue
        base_dir = os.path.dirname(path)
        rel = safe_relpath(path)
        for target, line_no in extract_markdown_links(content):
            if is_skippable_link_target(target):
                continue
            target_no_anchor = target.split("#", 1)[0]
            if not target_no_anchor:
                continue
            resolved = os.path.normpath(os.path.join(base_dir, target_no_anchor))
            if not os.path.exists(resolved):
                errors.append(
                    f"BROKEN LINK: {rel}:{line_no}: target not found: {target}"
                )


def check_terminology(doc_files, errors):
    """Report camelCase variants of the five canonical multi-word terms.

    Skips frontmatter and fenced code blocks to avoid false positives in
    YAML keys, code samples, and quoted schema field names.
    """
    for path in doc_files:
        if not path.endswith(".md"):
            continue
        content = _read_text(path)
        if not content:
            continue
        rel = safe_relpath(path)
        in_frontmatter = False
        in_code_fence = False
        for line_no, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped == "---":
                if line_no == 1 or in_frontmatter:
                    in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter:
                continue
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_code_fence = not in_code_fence
                continue
            if in_code_fence:
                continue
            for match in CAMELCASE_RE.finditer(line):
                variant = match.group(1)
                canonical = CAMELCASE_TO_CANONICAL[variant]
                errors.append(
                    f"BAD TERMINOLOGY: {rel}:{line_no}: '{variant}' should be '{canonical}'"
                )


def check_schema_version(doc_files, errors):
    """Report Markdown frontmatter and JSONL records whose schema_version does not match."""
    fm_pattern = re.compile(r"^\s*schema_version:\s*(\S+)\s*$", re.MULTILINE)

    for path in doc_files:
        rel = safe_relpath(path)
        if path.endswith(".md"):
            content = _read_text(path)
            if not content:
                continue
            fm, _ = extract_frontmatter(content)
            if fm is None:
                continue
            m = fm_pattern.search(fm)
            if not m:
                continue
            version = m.group(1).strip().strip('"').strip("'")
            if version != EXPECTED_SCHEMA_VERSION:
                errors.append(
                    f"SCHEMA VERSION: {rel}: found '{version}', expected '{EXPECTED_SCHEMA_VERSION}'"
                )
        elif path.endswith(".jsonl"):
            content = _read_text(path)
            if not content:
                continue
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                version = record.get("schema_version")
                if version is None:
                    continue
                if str(version).strip() != EXPECTED_SCHEMA_VERSION:
                    errors.append(
                        f"SCHEMA VERSION: {rel}:{line_no}: found '{version}', "
                        f"expected '{EXPECTED_SCHEMA_VERSION}'"
                    )


def check_skill_size(target, errors, warnings):
    """Enforce the SKILL.md installed-weight budget.

    Fails only above the hard ceiling. Inside the tolerance band
    (target < size <= hard) it records an advisory instead of an error.
    """
    skill_path = os.path.join(target, "SKILL.md") if os.path.isdir(target) else None
    if skill_path and os.path.isfile(skill_path):
        size = os.path.getsize(skill_path)
        if size > SKILL_SIZE_HARD:
            errors.append(
                f"SKILL SIZE: SKILL.md is {size} bytes, exceeds "
                f"{SKILL_SIZE_HARD} byte hard ceiling"
            )
        elif size > SKILL_SIZE_TARGET:
            warnings.append(
                f"SKILL SIZE: SKILL.md is {size} bytes, over the "
                f"{SKILL_SIZE_TARGET} byte target (hard ceiling "
                f"{SKILL_SIZE_HARD}); trim soon or move content to references/"
            )


def check_surface_growth(target, warnings):
    """Advisory-only: warn when scripts/ or references/ grow past their budget.

    Counts top-level files only and never appends to errors, so it cannot fail
    the audit. Silent when the directory is absent (e.g. running against a
    fixture subtree), so it only fires at the repo root.
    """
    if not os.path.isdir(target):
        return
    for subdir, ext, limit in (
        ("scripts", ".py", SCRIPTS_COUNT_WARN),
        ("references", ".md", REFERENCES_COUNT_WARN),
    ):
        directory = os.path.join(target, subdir)
        if not os.path.isdir(directory):
            continue
        count = sum(
            1
            for name in os.listdir(directory)
            if name.endswith(ext) and os.path.isfile(os.path.join(directory, name))
        )
        if count > limit:
            warnings.append(
                "SURFACE GROWTH: {sub}/*{ext} count is {count}, over the {limit} "
                "advisory budget; merge a new concept into an existing file "
                "before adding more".format(
                    sub=subdir, ext=ext, count=count, limit=limit
                )
            )


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "."

    if not os.path.exists(target):
        print(f"FAIL: path not found: {target}")
        sys.exit(1)

    errors = []
    warnings = []
    doc_files = list(find_doc_files(target))

    check_links(doc_files, errors)
    check_terminology(doc_files, errors)
    check_schema_version(doc_files, errors)
    check_skill_size(target, errors, warnings)
    check_surface_growth(target, warnings)

    for warn in warnings:
        print(f"WARN: {warn}")

    if errors:
        print(f"FAIL: {len(errors)} documentation issue(s) found under {target}:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    md_count = sum(1 for p in doc_files if p.endswith(".md"))
    jsonl_count = sum(1 for p in doc_files if p.endswith(".jsonl"))
    print(
        f"PASS: audited {md_count} markdown and {jsonl_count} jsonl file(s) "
        f"under {target}; no issues found"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
