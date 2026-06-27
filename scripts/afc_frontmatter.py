#!/usr/bin/env python3
"""Shared frontmatter parsing helpers for AFC scripts.

The protocol uses a deliberately small YAML subset. Consumers choose one of
three explicit representations instead of carrying private parser variants:

- flat: nested keys use dot notation and scalar values remain strings;
- nested: dot-notation keys are reconstructed as dictionaries;
- structured: indentation, known lists, and boolean values are parsed.
"""

import os


DEFAULT_LIST_KEYS = frozenset([
    "blockers",
    "changed_files",
    "evidence_checked",
    "evidence_refs",
    "follow_up",
    "inputs",
    "source_artifacts",
])

# Identifier / schema keys that must stay strings. An unquoted YAML bool
# literal (yes/no/true/false) is a valid AFC identifier (e.g. task_id: yes),
# and coercing it to a Python bool would break the downstream string identity
# comparisons (task_id/agent_name matching, .strip(), etc.). Boolean guardrail
# and permission fields are NOT listed here, so they still coerce to real
# bools for the `is True` checks in afc_inbox_validation / afc_validation.
DEFAULT_STRING_KEYS = frozenset([
    "task_id",
    "agent_name",
    "trace_id",
    "schema",
    "schema_version",
])


def _strip_quotes(value):
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in ("'", '"')
    ):
        return value[1:-1]
    return value


def _read_document(filepath):
    try:
        with open(filepath, "r", encoding="utf-8-sig") as handle:
            content = handle.read()
    except OSError as exc:
        return None, None, None, "could not read {}: {}".format(filepath, exc)

    lines = content.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip():
            start = index
            break
    if start is None:
        return content, lines, None, "empty file: {}".format(filepath)
    if lines[start].strip() != "---":
        return content, lines, None, "no frontmatter in {}".format(filepath)

    end = None
    for index in range(start + 1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return content, lines, (start, None), (
            "unterminated frontmatter in {}".format(filepath)
        )
    return content, lines, (start, end), None


def parse_flat_lines(lines, strict=True):
    """Parse frontmatter lines into a dot-notation dictionary."""
    data = {}
    current_key = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("- "):
            continue
        if ":" not in line:
            if strict:
                return None, "malformed frontmatter line: {}".format(raw_line)
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        if not key:
            if strict:
                return None, "empty key in frontmatter"
            continue

        indent = len(raw_line) - len(raw_line.lstrip())
        if indent > 0 and current_key:
            data["{}.{}".format(current_key, key)] = value
            continue

        data[key] = value
        current_key = key if value == "" else None
    return data, None


def nest_dotted_keys(data):
    """Return a copy with dot-notation keys reconstructed as dictionaries."""
    nested = {}
    for key, value in data.items():
        if "." not in key:
            nested[key] = value
            continue
        parent, child = key.split(".", 1)
        current = nested.get(parent)
        if not isinstance(current, dict):
            current = {}
            nested[parent] = current
        current[child] = value
    return nested


def parse_structured_lines(lines, list_keys=None, string_keys=None):
    """Parse the protocol's structured YAML subset."""
    list_keys = DEFAULT_LIST_KEYS if list_keys is None else frozenset(list_keys)
    string_keys = DEFAULT_STRING_KEYS if string_keys is None else frozenset(string_keys)
    data = {}
    errors = []
    stack = [(0, data)]

    for line_number, line in enumerate(lines, 1):
        if not line.strip() or line.strip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        while len(stack) > 1 and stack[-1][0] > indent:
            stack.pop()
        parent = stack[-1][1]

        if stripped.startswith("- "):
            if isinstance(parent, list):
                parent.append(_strip_quotes(stripped[2:].strip()))
            else:
                errors.append(
                    "line {}: list item outside list".format(line_number)
                )
            continue

        if ":" not in stripped or not isinstance(parent, dict):
            errors.append("line {}: invalid YAML".format(line_number))
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        if not key:
            errors.append("line {}: empty key".format(line_number))
            continue
        if key in parent:
            errors.append(
                "line {}: duplicate key {}".format(line_number, key)
            )

        if value == "":
            child = [] if key in list_keys else {}
            parent[key] = child
            stack.append((indent + 2, child))
            continue

        # Identifier/schema keys keep their string value (see DEFAULT_STRING_KEYS);
        # only non-identifier values get YAML bool coercion.
        if key not in string_keys:
            lowered = value.lower()
            if lowered in {"yes", "true"}:
                value = True
            elif lowered in {"no", "false"}:
                value = False
        parent[key] = value

    return data, errors


def parse_frontmatter_flat(filepath, strict=True, include_content=False):
    """Parse a file into the flat representation."""
    content, lines, bounds, error = _read_document(filepath)
    if error:
        if include_content:
            return None, content or "", error
        return None, error

    start, end = bounds
    data, parse_error = parse_flat_lines(lines[start + 1:end], strict=strict)
    if parse_error:
        parse_error = "{} in {}".format(parse_error, filepath)
    if include_content:
        return data, content, parse_error
    return data, parse_error


def parse_frontmatter_nested(filepath, strict=True):
    """Parse a file into the nested string representation."""
    data, error = parse_frontmatter_flat(filepath, strict=strict)
    if error or data is None:
        return data, error
    return nest_dotted_keys(data), None


def extract_structured_frontmatter(filepath):
    """Return structured data, body text, and parse errors.

    Files without a frontmatter marker return ``(None, content, [])``. An
    unterminated block that looks like coordination data is returned with a
    missing-closing-marker error, matching the formal validator contract.
    """
    try:
        with open(filepath, "r", encoding="utf-8-sig") as handle:
            content = handle.read()
    except OSError:
        return None, "", []

    lines = content.splitlines()
    if not lines:
        return None, content, []

    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines) or lines[start].strip() != "---":
        return None, content, []

    end = None
    for index in range(start + 1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break

    if end is None:
        data, errors = parse_structured_lines(lines[start + 1:])
        coordination_keys = {"agent_name", "schema", "schema_type", "task_id"}
        if coordination_keys.intersection(data):
            errors.append("Missing closing --- for frontmatter")
            return data, "", errors
        return None, content, []

    data, errors = parse_structured_lines(lines[start + 1:end])
    body = "\n".join(lines[end + 1:])
    return data, body, errors


def parse_frontmatter_structured(filepath):
    """Return structured data and parse errors without the document body."""
    data, _, errors = extract_structured_frontmatter(filepath)
    return data, errors


def read_frontmatter_body(filepath):
    """Return text after the closing frontmatter marker, or an empty string."""
    _, body, _ = extract_structured_frontmatter(filepath)
    return body
