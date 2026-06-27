#!/usr/bin/env python3
"""Regression tests for the blast_radius classifier (afc-blast-radius.py).

The classifier reads a declared file list (no diff exists yet at route time)
and returns low/medium/high with evidence. These tests cover the four lanes the
MOA value gate depends on: domain-risk high, fan-out high, low-risk docs/isolated,
and fail-soft on unclassifiable input.
"""

import json
import os
import subprocess
import sys
import tempfile


REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SCRIPT = os.path.join(REPO_ROOT, "scripts", "afc-blast-radius.py")

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("  [PASS] {}".format(label))
    else:
        FAIL += 1
        print("  [FAIL] {}: {}".format(label, detail))


def run_classifier(files, repo_root):
    cmd = [sys.executable, "-B", SCRIPT,
           "--files", *files, "--repo-root", repo_root, "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout) if result.stdout else {}
    return result, data


def test_high_domain():
    # A file whose path contains a sensitive domain keyword -> high.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        auth_file = os.path.join(repo, "auth_login.py")
        with open(auth_file, "w", encoding="utf-8") as handle:
            handle.write("def login():\n    pass\n")
        result, data = run_classifier(["auth_login.py"], repo)
        check(
            "domain-keyword file is high",
            data.get("blast_radius") == "high"
            and any("auth" in s for s in data.get("evidence", {}).get("domain", [])),
            data,
        )


def test_high_fanout():
    # A module imported by >= FANOUT_THRESHOLD others, no test sibling -> high.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "x@y.z"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "x"], check=True)
        core = os.path.join(repo, "core_logic.py")
        with open(core, "w", encoding="utf-8") as handle:
            handle.write("def f():\n    pass\n")
        for idx in range(3):
            with open(os.path.join(repo, "use_{}.py".format(idx)), "w", encoding="utf-8") as handle:
                handle.write("import core_logic\n")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"], check=True)
        result, data = run_classifier(["core_logic.py"], repo)
        check(
            "high-fanout module without test is high",
            data.get("blast_radius") == "high"
            and len(data.get("evidence", {}).get("fanout", [])) >= 1,
            data,
        )


def test_low_isolated_with_test():
    # A lone module that has a test sibling -> low (easy to verify + small radius).
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "x@y.z"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "x"], check=True)
        with open(os.path.join(repo, "feature_x.py"), "w", encoding="utf-8") as handle:
            handle.write("def x():\n    pass\n")
        with open(os.path.join(repo, "test_feature_x.py"), "w", encoding="utf-8") as handle:
            handle.write("assert True\n")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"], check=True)
        result, data = run_classifier(["feature_x.py"], repo)
        check(
            "isolated module with test sibling is low",
            data.get("blast_radius") == "low",
            data,
        )


def test_low_docs():
    # Documentation files are inherently low-risk regardless of content words.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        with open(os.path.join(repo, "guide.md"), "w", encoding="utf-8") as handle:
            # The word "authority" inside a doc must not inflate the radius.
            handle.write("# Guide\n\nThe coordinator holds final authority.\n")
        result, data = run_classifier(["guide.md"], repo)
        check(
            "markdown doc is low even with authority keyword",
            data.get("blast_radius") == "low",
            data,
        )


def test_path_substring_not_misclassified():
    # Review Task 3: "/test" substring and "auth"/"lock" word-fragments must not
    # misclassify real source. Path/test matching uses path segments; domain
    # matching uses word boundaries.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        os.makedirs(os.path.join(repo, "app"))
        with open(os.path.join(repo, "app", "testimonials.py"), "w", encoding="utf-8") as handle:
            handle.write("def feed():\n    pass\n")
        result, data = run_classifier(["app/testimonials.py"], repo)
        check(
            "app/testimonials.py not treated as docs-or-test",
            "docs-or-test" not in ",".join(data.get("evidence", {}).get("low_signals", [])),
            data,
        )
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        with open(os.path.join(repo, "author_block.py"), "w", encoding="utf-8") as handle:
            # Both "author" (auth fragment) and "block" (lock fragment) must NOT
            # count as domain hits now that matching is word-boundary.
            handle.write("def author_of_block():\n    pass\n")
        result, data = run_classifier(["author_block.py"], repo)
        check(
            "author_block.py not inflated by auth/lock word-fragments",
            len(data.get("evidence", {}).get("domain", [])) == 0,
            data,
        )


def test_repo_under_tests_dir_not_misclassified():
    # PR review #1: when the repo itself lives under a directory named tests/,
    # docs/, etc., the absolute-path check used to classify EVERY declared file
    # as docs-or-test, skipping domain/fan-out. Must use repo-relative paths.
    base = tempfile.mkdtemp(prefix="afc-br-")
    repo = os.path.join(base, "tests", "proj")
    os.makedirs(os.path.join(repo, "src"))
    with open(os.path.join(repo, "src", "auth.py"), "w", encoding="utf-8") as handle:
        handle.write("def login():\n    pass\n")
    result, data = run_classifier(["src/auth.py"], repo)
    check(
        "auth.py under .../tests/proj still classifies high (not docs-or-test)",
        data.get("blast_radius") == "high"
        and any("auth" in s for s in data.get("evidence", {}).get("domain", [])),
        data,
    )


def test_package_qualified_import_fanout():
    # PR review #2: `from pkg.core import f` was missed by the fan-out grep, so
    # a shared package module counted as isolated/low. Must count it.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "x@y.z"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "x"], check=True)
        os.makedirs(os.path.join(repo, "pkg"))
        with open(os.path.join(repo, "pkg", "__init__.py"), "w", encoding="utf-8"):
            pass
        with open(os.path.join(repo, "pkg", "core.py"), "w", encoding="utf-8") as handle:
            handle.write("def f():\n    pass\n")
        for idx in range(3):
            with open(os.path.join(repo, "use_{}.py".format(idx)), "w", encoding="utf-8") as handle:
                handle.write("from pkg.core import f\n")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"], check=True)
        result, data = run_classifier(["pkg/core.py"], repo)
        check(
            "package-qualified imports (from pkg.core) counted as fan-out",
            data.get("blast_radius") == "high"
            and len(data.get("evidence", {}).get("fanout", [])) >= 1,
            data,
        )


def test_package_initializer_fanout():
    # PR review #5: pkg/__init__.py had stem "__init__", so fan-out looked for
    # "import __init__" (never written) instead of "import pkg", misclassifying
    # a widely-imported package initializer as isolated/low.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "x@y.z"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "x"], check=True)
        os.makedirs(os.path.join(repo, "pkg"))
        with open(os.path.join(repo, "pkg", "__init__.py"), "w", encoding="utf-8") as handle:
            handle.write("VERSION = 1\n")
        for idx in range(3):
            with open(os.path.join(repo, "use_{}.py".format(idx)), "w", encoding="utf-8") as handle:
                handle.write("import pkg\n")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"], check=True)
        result, data = run_classifier(["pkg/__init__.py"], repo)
        check(
            "package initializer (__init__.py) fan-out counts import pkg",
            data.get("blast_radius") == "high"
            and len(data.get("evidence", {}).get("fanout", [])) >= 1,
            data,
        )


def test_domain_keyword_on_repo_relative_path():
    # PR review #6: domain keyword path check used the absolute path, so a
    # checkout under /tmp/auth/proj made src/widget.py hit the auth keyword.
    # Must match on the declared (repo-relative) path; content read stays abs.
    base = tempfile.mkdtemp(prefix="afc-br-")
    repo = os.path.join(base, "auth", "proj")
    os.makedirs(os.path.join(repo, "src"))
    with open(os.path.join(repo, "src", "widget.py"), "w", encoding="utf-8") as handle:
        handle.write("def render():\n    pass\n")
    result, data = run_classifier(["src/widget.py"], repo)
    check(
        "widget.py under .../auth/proj not inflated by repo path keyword",
        len(data.get("evidence", {}).get("domain", [])) == 0,
        data,
    )


def test_fanout_dedups_single_file_multiple_imports():
    # PR review #7: one file with three import lines for the same module
    # (import core / import core as c / from core import f) counted as fanout=3,
    # crossing the threshold. Must count unique importer FILES.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "x@y.z"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "x"], check=True)
        with open(os.path.join(repo, "core.py"), "w", encoding="utf-8") as handle:
            handle.write("def f():\n    pass\n")
        with open(os.path.join(repo, "single_user.py"), "w", encoding="utf-8") as handle:
            handle.write("import core\nimport core as c\nfrom core import f\n")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"], check=True)
        result, data = run_classifier(["core.py"], repo)
        # fanout evidence stays empty: one importer is below the threshold.
        check(
            "single file with 3 import lines does not cross fan-out threshold",
            len(data.get("evidence", {}).get("fanout", [])) == 0,
            data,
        )


def test_fanout_disambiguates_same_basename_packages():
    # PR review #9: pkg_a/core.py and pkg_b/core.py share basename 'core'; the
    # old grep matched any .core import. Changing pkg_a/core.py while three
    # files import pkg_b.core must NOT count pkg_b's importers.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "x@y.z"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "x"], check=True)
        for pkg in ("pkg_a", "pkg_b"):
            os.makedirs(os.path.join(repo, pkg))
            with open(os.path.join(repo, pkg, "__init__.py"), "w", encoding="utf-8"):
                pass
        with open(os.path.join(repo, "pkg_a", "core.py"), "w", encoding="utf-8") as handle:
            handle.write("def fa():\n    pass\n")
        with open(os.path.join(repo, "pkg_b", "core.py"), "w", encoding="utf-8") as handle:
            handle.write("def fb():\n    pass\n")
        for idx in range(3):
            with open(os.path.join(repo, "use_{}.py".format(idx)), "w", encoding="utf-8") as handle:
                handle.write("from pkg_b.core import fb\n")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"], check=True)
        result, data = run_classifier(["pkg_a/core.py"], repo)
        check(
            "pkg_a/core.py not inflated by pkg_b.core importers",
            len(data.get("evidence", {}).get("fanout", [])) == 0,
            data,
        )


def test_fanout_counts_package_relative_imports():
    # PR review #11: from .core import f (package-relative) was missed when the
    # module was resolved to its dotted path pkg.core. Now counted via ast.parse.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "x@y.z"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "x"], check=True)
        os.makedirs(os.path.join(repo, "pkg"))
        with open(os.path.join(repo, "pkg", "__init__.py"), "w", encoding="utf-8"):
            pass
        with open(os.path.join(repo, "pkg", "core.py"), "w", encoding="utf-8") as handle:
            handle.write("def f():\n    pass\n")
        for idx in range(3):
            with open(os.path.join(repo, "pkg", "mod_{}.py".format(idx)), "w", encoding="utf-8") as handle:
                handle.write("from .core import f\n")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"], check=True)
        result, data = run_classifier(["pkg/core.py"], repo)
        check(
            "package-relative imports (from .core) counted as fan-out",
            data.get("blast_radius") == "high"
            and len(data.get("evidence", {}).get("fanout", [])) >= 1,
            data,
        )


def test_fanout_counts_package_member_imports():
    # PR review #12: `from pkg import core` (member import of a submodule) was
    # missed by every regex iteration. ast.parse resolves it exactly.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        os.makedirs(os.path.join(repo, "pkg"))
        with open(os.path.join(repo, "pkg", "__init__.py"), "w", encoding="utf-8"):
            pass
        with open(os.path.join(repo, "pkg", "core.py"), "w", encoding="utf-8") as handle:
            handle.write("def f():\n    pass\n")
        for idx in range(3):
            with open(os.path.join(repo, "use_{}.py".format(idx)), "w", encoding="utf-8") as handle:
                handle.write("from pkg import core\n")
        result, data = run_classifier(["pkg/core.py"], repo)
        check(
            "package member imports (from pkg import core) counted as fan-out",
            data.get("blast_radius") == "high"
            and len(data.get("evidence", {}).get("fanout", [])) >= 1,
            data,
        )


def test_fail_soft_nonexistent():
    # A path that does not exist must not crash or be mistaken for isolated.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        result, data = run_classifier(["does/not/exist.py"], repo)
        check(
            "nonexistent file fails soft to medium",
            result.returncode == 0 and data.get("blast_radius") == "medium",
            data or result.stderr,
        )


def test_at_filelist():
    # @filelist form reads paths one per line.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        with open(os.path.join(repo, "auth_service.py"), "w", encoding="utf-8") as handle:
            handle.write("def authenticate():\n    pass\n")
        listfile = os.path.join(repo, "paths.txt")
        with open(listfile, "w", encoding="utf-8") as handle:
            handle.write("auth_service.py\n")
        result = subprocess.run(
            [sys.executable, "-B", SCRIPT,
             "--files", "@" + listfile, "--repo-root", repo, "--json"],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout) if result.stdout else {}
        check(
            "@filelist reads paths and classifies",
            data.get("blast_radius") == "high",
            data or result.stderr,
        )


def test_multifile_doc_plus_source_is_medium():
    # Regression: a low docs file must not drag a whole task to low when a real
    # source file lands on the medium fallback. Otherwise substantive work
    # edited alongside a changelog would skip MOA cross-check.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        with open(os.path.join(repo, "CHANGELOG.md"), "w", encoding="utf-8") as handle:
            handle.write("# changes\n")
        with open(os.path.join(repo, "app.js"), "w", encoding="utf-8") as handle:
            handle.write("function f() {}\n")
        result, data = run_classifier(["CHANGELOG.md", "app.js"], repo)
        check(
            "doc + real source stays medium, not dragged to low",
            data.get("blast_radius") == "medium",
            data,
        )


def test_multifile_pure_docs_is_low():
    # Multiple docs files with no source -> still low.
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        with open(os.path.join(repo, "guide.md"), "w", encoding="utf-8") as handle:
            handle.write("# guide\n")
        with open(os.path.join(repo, "notes.md"), "w", encoding="utf-8") as handle:
            handle.write("# notes\n")
        result, data = run_classifier(["guide.md", "notes.md"], repo)
        check(
            "multiple docs with no source stay low",
            data.get("blast_radius") == "low",
            data,
        )


def test_multifile_high_dominates():
    # A high-risk source file plus a low doc -> high wins (the risky part
    # governs the whole task).
    with tempfile.TemporaryDirectory(prefix="afc-br-") as repo:
        with open(os.path.join(repo, "auth_login.py"), "w", encoding="utf-8") as handle:
            handle.write("def login():\n    pass\n")
        with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("# read me\n")
        result, data = run_classifier(["auth_login.py", "README.md"], repo)
        check(
            "high source + low doc -> high dominates",
            data.get("blast_radius") == "high",
            data,
        )


def main():
    print("Running blast-radius classifier regression tests...")
    test_high_domain()
    test_high_fanout()
    test_low_isolated_with_test()
    test_low_docs()
    test_path_substring_not_misclassified()
    test_repo_under_tests_dir_not_misclassified()
    test_package_qualified_import_fanout()
    test_package_initializer_fanout()
    test_domain_keyword_on_repo_relative_path()
    test_fanout_dedups_single_file_multiple_imports()
    test_fanout_disambiguates_same_basename_packages()
    test_fanout_counts_package_relative_imports()
    test_fanout_counts_package_member_imports()
    test_fail_soft_nonexistent()
    test_at_filelist()
    test_multifile_doc_plus_source_is_medium()
    test_multifile_pure_docs_is_low()
    test_multifile_high_dominates()
    print("\nResults: {} passed, {} failed".format(PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
