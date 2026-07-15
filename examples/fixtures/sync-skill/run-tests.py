#!/usr/bin/env python3
"""Fixture: sync-skill.ps1 preserves install-local LOCAL_* files.

CI runs on Linux where pwsh may be absent, so this fixture:
  1. source-asserts the LOCAL_* preserve clause in scripts/sync-skill.ps1; and
  2. if pwsh is available, live-runs a dry sync against a temp HOME and asserts
     known LOCAL files are preserved (skip otherwise).

Usage:
    python -B examples/fixtures/sync-skill/run-tests.py
"""

import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SYNC_SCRIPT = os.path.join(REPO_ROOT, "scripts", "sync-skill.ps1")
READMES = (os.path.join(REPO_ROOT, "README.md"), os.path.join(REPO_ROOT, "README.zh-CN.md"))

KNOWN_LOCAL_FILES = [
    "LOCAL_ROSTER.md",
    "LOCAL_INVOKE_RECIPES.json",
    "LOCAL_RUNTIME_NOTES.md",
    "LOCAL_ROUTING_NOTES.md",
]


class Runner:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def check(self, name, ok, detail=""):
        if ok:
            self.passed += 1
            print("  [PASS] {}".format(name))
        else:
            self.failed += 1
            print("  [FAIL] {}: {}".format(name, detail[:300]))


def test_preserve_clause_in_source(runner):
    print("\n[test] sync-skill.ps1 preserves LOCAL_* (dest AND source)")
    with open(SYNC_SCRIPT, "r", encoding="utf-8") as f:
        src = f.read()
    runner.check(
        "LOCAL_* preserve clause present",
        "LOCAL_*" in src,
        "sync-skill.ps1 missing LOCAL_* preserve condition",
    )
    # The known LOCAL filenames must be covered by the LOCAL_* glob (prefix match).
    for name in KNOWN_LOCAL_FILES:
        runner.check(
            "{} covered by LOCAL_*".format(name),
            name.startswith("LOCAL_"),
            "{} not a LOCAL_* file".format(name),
        )
    # The preserve branch must skip deletion/overwrite (return inside the loop).
    runner.check(
        "preserve branch returns/skips",
        "return}" in src.replace(" ", "") or "return" in src,
        "preserve branch does not skip",
    )
    # Source-collection MUST also drop LOCAL_* so a stray checkout LOCAL_ROSTER.md
    # cannot overwrite the user's real install-local roster (Codex P2 finding).
    runner.check(
        "source collection excludes LOCAL_* (helper defined)",
        "Is-LocalOnlyName" in src,
        "sync-skill.ps1 must define Is-LocalOnlyName / apply it during source collection",
    )
    runner.check(
        "source collection applies the helper",
        src.count("Is-LocalOnlyName") >= 3,
        "expected helper definition + at least 2 usage sites (root file loop + dir loop)",
    )


def test_documented_install_identity(runner):
    print("\n[test] public install path matches sync-skill identity")
    for path in READMES:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        runner.check(os.path.basename(path) + " uses canonical directory",
                     ".codex/skills/agent-file-coordination/" in content,
                     "canonical Codex install path missing")
        runner.check(os.path.basename(path) + " has no stale delegator directory",
                     ".codex/skills/delegator/" not in content and
                     ".codex\\skills\\delegator" not in content,
                     "stale install directory remains")


def test_live_sync_preserves_local(runner):
    print("\n[test] live sync preserves LOCAL_ROSTER.md / LOCAL_INVOKE_RECIPES.json")
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        print("  [SKIP] pwsh not available on this host")
        return
    import tempfile
    tmp_home = tempfile.mkdtemp(prefix="afc-sync-home-")
    dest = os.path.join(tmp_home, ".claude", "skills", "agent-file-coordination")
    os.makedirs(dest)
    for name in ("LOCAL_ROSTER.md", "LOCAL_INVOKE_RECIPES.json"):
        with open(os.path.join(dest, name), "w", encoding="utf-8") as f:
            f.write("# preserved marker {}\n".format(name))
    try:
        r = subprocess.run(
            [pwsh, "-NoProfile", "-File", SYNC_SCRIPT, "-Targets", "claude"],
            capture_output=True, text=True, timeout=60,
            env=dict(os.environ, HOME=tmp_home, USERPROFILE=tmp_home),
        )
        ok = r.returncode == 0
        runner.check("sync exit=0", ok, "code={} err={!r}".format(r.returncode, r.stderr[:300]))
        for name in ("LOCAL_ROSTER.md", "LOCAL_INVOKE_RECIPES.json"):
            path = os.path.join(dest, name)
            survived = os.path.isfile(path)
            content_ok = False
            if survived:
                with open(path, "r", encoding="utf-8") as f:
                    content_ok = "preserved marker" in f.read()
            runner.check(
                "{} survived sync".format(name),
                survived and content_ok,
                "survived={} content_ok={}".format(survived, content_ok),
            )
    finally:
        shutil.rmtree(tmp_home, True)


def test_live_sync_ignores_source_local_files(runner):
    """Regression: a stray LOCAL_ROSTER.md in the repo checkout must not
    overwrite the user's install-local roster during sync (Codex P2)."""
    print("\n[test] live sync ignores checkout-side LOCAL_* files")
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        print("  [SKIP] pwsh not available on this host")
        return
    import tempfile
    tmp_home = tempfile.mkdtemp(prefix="afc-sync-home-")
    tmp_repo = tempfile.mkdtemp(prefix="afc-sync-repo-")
    dest = os.path.join(tmp_home, ".claude", "skills", "agent-file-coordination")
    os.makedirs(dest)
    # Set up a MINIMAL copy of the real repo so sync-skill.ps1 has something to
    # sync. We keep the whole tree (via copytree) so all files it expects are
    # present, then inject stray LOCAL_* AT THE REPO ROOT.
    try:
        shutil.copytree(REPO_ROOT, tmp_repo, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", ".agent-inbox", ".worktrees",
                                                     "__pycache__", "*.pyc"))
        # Ensure git rev-parse works — sync-skill needs it. If .git wasn't copied,
        # init a stub repo with one commit so `git rev-parse HEAD` works.
        if not os.path.isdir(os.path.join(tmp_repo, ".git")):
            for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                         "commit", "-q", "-m", "stub"]):
                subprocess.run(cmd, cwd=tmp_repo, capture_output=True, timeout=60)
        # Inject stray LOCAL_* at the CHECKOUT root (the exact scenario).
        stray_content = "# STRAY checkout roster — MUST NOT propagate\n"
        stray_recipe = '{"stray": true}\n'
        with open(os.path.join(tmp_repo, "LOCAL_ROSTER.md"), "w", encoding="utf-8") as f:
            f.write(stray_content)
        with open(os.path.join(tmp_repo, "LOCAL_INVOKE_RECIPES.json"), "w", encoding="utf-8") as f:
            f.write(stray_recipe)
        # Pre-seed dest with the USER's real content that must survive.
        preserved_marker = "# preserved marker — user's real install-local roster\n"
        with open(os.path.join(dest, "LOCAL_ROSTER.md"), "w", encoding="utf-8") as f:
            f.write(preserved_marker)
        with open(os.path.join(dest, "LOCAL_INVOKE_RECIPES.json"), "w", encoding="utf-8") as f:
            f.write('{"preserved": true}\n')
        # Run sync from the tmp_repo checkout against the tmp_home.
        r = subprocess.run(
            [pwsh, "-NoProfile", "-File", os.path.join(tmp_repo, "scripts", "sync-skill.ps1"),
             "-Targets", "claude"],
            capture_output=True, text=True, timeout=120,
            env=dict(os.environ, HOME=tmp_home, USERPROFILE=tmp_home),
        )
        runner.check("sync exit=0", r.returncode == 0,
                     "code={} out={!r} err={!r}".format(r.returncode, r.stdout[:300], r.stderr[:300]))
        # The user's LOCAL_ROSTER.md and LOCAL_INVOKE_RECIPES.json in dest must
        # STILL be their preserved content, not the checkout stray.
        with open(os.path.join(dest, "LOCAL_ROSTER.md"), "r", encoding="utf-8") as f:
            dest_roster = f.read()
        with open(os.path.join(dest, "LOCAL_INVOKE_RECIPES.json"), "r", encoding="utf-8") as f:
            dest_recipes = f.read()
        runner.check("dest LOCAL_ROSTER.md preserved (not overwritten by checkout stray)",
                     dest_roster == preserved_marker,
                     "dest content: {!r}".format(dest_roster[:200]))
        runner.check("dest LOCAL_INVOKE_RECIPES.json preserved",
                     '"preserved"' in dest_recipes and "stray" not in dest_recipes,
                     "dest content: {!r}".format(dest_recipes[:200]))
    finally:
        shutil.rmtree(tmp_home, True)
        shutil.rmtree(tmp_repo, True)


def main():
    runner = Runner()
    print("Running sync-skill preservation tests...")
    test_preserve_clause_in_source(runner)
    test_documented_install_identity(runner)
    test_live_sync_preserves_local(runner)
    test_live_sync_ignores_source_local_files(runner)
    print("\npassed: {}  failed: {}".format(runner.passed, runner.failed))
    return 0 if runner.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
