#!/usr/bin/env python3
"""Estimate the blast radius of a planned change from a declared file list.

Routing happens BEFORE code is written, so there is no diff to read. Instead the
coordinator declares the files it expects to touch (mirrors `afc-lite.py
--allow-files`) and this script classifies the change's blast radius from those
files alone. The output feeds `routing.blast_radius` so the MOA gate stays
objective and scriptable, never an inflatable coordinator score.

Strategy (combinatorial, each checkable by a read-only scan):
  - domain risk: a declared file path or its current content matches a sensitive
    keyword (auth/payment/migration/lock/concurrency/token/secret).
  - fan-out: a Python module is imported by >= FANOUT_THRESHOLD other files.
  - testability: the declared file has no sibling test_* file.

Result: `low` / `medium` / `high` with the evidence that fired. Failures on one
file are ignored (fail-soft) so a brittle path never blocks routing.
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys


# Sensitive-domain keywords. Keep the list short, auditable, and literal.
DOMAIN_KEYWORDS = (
    "auth", "permission", "password", "payment", "billing",
    "migration", "lock", "concurrency", "token", "secret",
    "credential", "crypto",
)

# A module imported by at least this many files counts as high fan-out.
FANOUT_THRESHOLD = 3


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def _domain_hit(declared_path, abs_path):
    # Match domain keywords on word boundaries so "auth" does not fire on
    # "author" and "lock" does not fire on "block". Path matching uses the
    # DECLARED (repo-relative) path, not the absolute path: otherwise a checkout
    # living under /tmp/auth/proj makes every file hit the auth keyword. Content
    # matching reads the absolute file.
    lowered_path = declared_path.lower().replace("\\", "/")
    content = _read_text(abs_path)
    low_content = content.lower()
    for kw in DOMAIN_KEYWORDS:
        path_re = r"(?:^|[/._\-])" + re.escape(kw) + r"(?:$|[/._\-])"
        if re.search(path_re, lowered_path):
            return kw
        if re.search(r"\b" + re.escape(kw) + r"\b", low_content):
            return kw
    return None


def _module_stem(path):
    base = os.path.basename(path)
    if not base.endswith(".py"):
        return None
    stem = base[:-3]
    # An __init__.py is imported via its package name (import pkg, not import
    # __init__), so its effective stem for fan-out / test-sibling lookups is the
    # parent directory. Otherwise a package initializer with many `import pkg`
    # users is misreported as isolated/low.
    if stem == "__init__":
        parent = os.path.basename(os.path.dirname(path))
        return parent if parent else stem
    return stem


def _imported_modules(file_path, file_pkg):
    """Parse a Python file with ast and yield dotted module names it imports.

    Resolves relative imports against file_pkg (the dotted package the file
    lives in). For `from .core import f` inside pkg/mod.py (file_pkg='pkg'),
    yields 'pkg.core'. For `from . import core` inside pkg/mod.py, yields 'pkg'
    (the package) AND 'pkg.core' (the imported name used as a submodule).
    For `from pkg import core`, yields 'pkg' and 'pkg.core'. Returns () on
    parse error (fail-soft)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
            tree = ast.parse(handle.read(), filename=file_path)
    except (OSError, SyntaxError, ValueError):
        return ()
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    seen.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # Resolve the module being imported from.
            if node.level == 0:
                # Absolute: from <module> import names
                base = node.module or ""
            else:
                # Relative: level dots climb up from file_pkg.
                # level=1 -> current package; level=2 -> parent; etc.
                parts = file_pkg.split(".") if file_pkg else []
                if node.level > len(parts):
                    base = node.module or ""
                else:
                    pkg_prefix = ".".join(parts[: len(parts) - node.level + 1]) if parts else ""
                    base = (pkg_prefix + "." + node.module) if node.module else pkg_prefix
            if base:
                seen.add(base)
            # `from X import Y` where Y is a submodule -> also count X.Y.
            # We cannot know statically if Y is a submodule or a name, so we
            # add both X and X.Y; the caller looks up the target exactly, so
            # false X.Y entries for plain names are harmless (they just won't
            # match a real file's dotted path).
            if base:
                for alias in node.names:
                    if alias.name and alias.name != "*":
                        seen.add(base + "." + alias.name)
    return seen


def _walk_python_files(repo_root):
    """Yield (abs_path, dotted_package) for every .py file under repo_root,
    skipping common non-source directories."""
    skip_dirs = {".git", "__pycache__", ".agent-inbox", "node_modules", ".venv", "venv"}
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        rel_root = os.path.relpath(root, repo_root).replace("\\", "/")
        pkg = rel_root.replace("/", ".") if rel_root != "." else ""
        for fname in files:
            if fname.endswith(".py"):
                yield os.path.join(root, fname), pkg


def _import_fanout(repo_root, dotted):
    """Count how many OTHER .py files import the module at `dotted` (e.g.
    'pkg_a.core'). Uses ast.parse so every import form is handled exactly:
    import X, from X import Y, from .X import Y, from pkg import X, etc.
    No regex, no string matching -- the AST is ground truth. Each file counts
    once (Review #7); same-basename cross-package is disambiguated by the full
    dotted path (Review #9)."""
    if not dotted or not os.path.isdir(repo_root):
        return 0
    target = dotted
    count = 0
    for file_path, file_pkg in _walk_python_files(repo_root):
        # Skip the module itself (self-import edge cases).
        file_dotted = _file_to_dotted(file_path, repo_root)
        if file_dotted == target:
            continue
        imported = _imported_modules(file_path, file_pkg)
        if target in imported:
            count += 1
    return count


def _file_to_dotted(file_path, repo_root):
    """Convert an absolute .py file path to its dotted module path."""
    try:
        rel = os.path.relpath(file_path, repo_root).replace("\\", "/")
    except ValueError:
        return ""
    base = os.path.basename(rel)
    if base == "__init__.py":
        parent = os.path.dirname(rel).replace("/", ".")
        return parent
    return rel[:-3].replace("/", ".")


def _dotted_module_path(declared_path, repo_root):
    """Convert a declared file path to its dotted module path for import lookup.
    pkg_a/core.py -> pkg_a.core ; core.py -> core ; pkg/__init__.py -> pkg.
    Non-.py files and paths that cannot be resolved return None."""
    if not declared_path.endswith(".py"):
        return None
    try:
        rel = os.path.relpath(
            os.path.abspath(os.path.join(repo_root or ".", declared_path)),
            os.path.abspath(repo_root or "."),
        )
    except ValueError:
        return None
    rel = rel.replace("\\", "/")
    base = os.path.basename(rel)
    if base == "__init__.py":
        # Package initializer: dotted path is the parent dir.
        parent = os.path.dirname(rel).replace("/", ".")
        return parent if parent else "__init__"
    return rel[:-3].replace("/", ".")


def _has_test_sibling(path):
    directory = os.path.dirname(path)
    stem = _module_stem(path)
    if not stem:
        base = os.path.basename(path)
        return base.endswith(".md") or "/docs/" in path.replace("\\", "/").lower()
    for candidate in ("test_" + stem + ".py", stem + "_test.py"):
        if os.path.isfile(os.path.join(directory, candidate)):
            return True
    return False


def classify(files, repo_root):
    """Classify blast radius. Priority: high signals outrank low; isolated
    (fan-out 0) is a low signal that intentionally overrides the absence of a
    test sibling, since a truly isolated file is easy to roll back even if the
    only test of it is the change itself.

    Multi-file aggregation rule: a single low file (docs/test) must not drag a
    whole task down to low if any real source file in the set lands on the
    medium fallback. Otherwise a task that edits substantive code alongside a
    changelog would be mis-routed as low and skip MOA cross-check."""
    evidence = {"domain": [], "fanout": [], "missing_test": [], "low_signals": []}
    high = False
    low = False
    has_source_medium = False  # a real source file with no high/low signal
    for raw in files:
        path = raw.strip()
        if not path:
            continue
        normalized = path if os.path.isabs(path) else os.path.join(repo_root or ".", path)
        normalized = os.path.abspath(normalized)
        # Match docs/test locations on the REPO-RELATIVE path, not the absolute
        # path: otherwise a repo living under .../tests/proj classifies every
        # declared file as docs-or-test and skips domain/fan-out checks.
        try:
            rel_path = os.path.relpath(normalized, repo_root)
        except ValueError:
            rel_path = normalized
        rel_low = rel_path.lower().replace("\\", "/")
        basename = rel_low.rsplit("/", 1)[-1]
        is_docs_or_test = (
            rel_low.endswith(".md")
            or rel_low.startswith("docs/") or "/docs/" in rel_low
            or rel_low.startswith("doc/") or "/doc/" in rel_low
            or rel_low.startswith("tests/") or "/tests/" in rel_low
            or rel_low.startswith("__tests__/") or "/__tests__/" in rel_low
            or rel_low.startswith("spec/") or "/spec/" in rel_low
            or basename.startswith("test_")
            or basename.endswith("_test.py")
        )
        # Docs/tests are inherently low-risk; never let a keyword inside a doc
        # (e.g. the word "authority" in a markdown guide) inflate the radius.
        if is_docs_or_test:
            evidence["low_signals"].append("{}:docs-or-test".format(path))
            low = True
            continue
        # Domain risk always wins for real source (auth/payment/migration/...).
        kw = _domain_hit(path, normalized)
        if kw:
            evidence["domain"].append("{}:{}".format(path, kw))
            high = True
        stem = _module_stem(normalized)
        dotted = _dotted_module_path(path, repo_root)
        fanout = _import_fanout(repo_root, dotted) if dotted else 0
        exists = os.path.isfile(normalized)
        file_signal = False
        if stem and fanout >= FANOUT_THRESHOLD:
            evidence["fanout"].append("{}:{}".format(path, fanout))
            high = True
            file_signal = True
        if stem and exists and fanout == 0:
            # Isolated Python module: small blast radius even with no test sibling.
            evidence["low_signals"].append("{}:isolated".format(path))
            low = True
            file_signal = True
        elif _has_test_sibling(normalized):
            evidence["low_signals"].append("{}:has-test".format(path))
            low = True
            file_signal = True
        elif stem and fanout >= 1:
            # Has dependents but no test: hard to verify, cross-check is worth it.
            evidence["missing_test"].append("{}:dependents={}".format(path, fanout))
            high = True
            file_signal = True
        if not file_signal:
            # A real source file (not docs/test) that hit no high or low signal:
            # it lands on the medium fallback and must keep the whole task >= medium.
            has_source_medium = True
        # Non-existent / unclassifiable files contribute nothing (fail-soft).
    if high:
        verdict = "high"
    elif has_source_medium:
        # Substantive code is being changed; do not let a sibling doc drag it
        # below medium even if no high signal fired.
        verdict = "medium"
    elif low:
        verdict = "low"
    else:
        verdict = "medium"
    return {"blast_radius": verdict, "evidence": evidence}


def main():
    parser = argparse.ArgumentParser(
        description="Classify a planned change's blast radius from declared files."
    )
    parser.add_argument("--files", nargs="+", required=True,
                        help="Declared files (or '@filelist' to read paths one per line).")
    parser.add_argument("--repo-root", default=".",
                        help="Repository root for import fan-out scanning.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    files = []
    for item in args.files:
        if item.startswith("@") and len(item) > 1:
            list_path = item[1:]
            try:
                with open(list_path, "r", encoding="utf-8") as handle:
                    files.extend(handle.read().splitlines())
            except OSError:
                continue
        else:
            files.append(item)

    repo_root = os.path.abspath(args.repo_root)
    result = classify(files, repo_root)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["blast_radius"])
        for key, values in result["evidence"].items():
            if values:
                print("  {}: {}".format(key, ", ".join(values)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
