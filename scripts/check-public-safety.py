import os
import sys
import re
import subprocess


FORBIDDEN_TRACKED_DIRS = [
    '.agent-inbox',
    '.worktrees',
    '.learnings',
    '.codebuddy',
    '.codex',
    '.claude',
    '.cursor',
    '.continue',
]

# Paths under which forbidden dirs are allowed (e.g. example fixtures)
FORBIDDEN_DIR_ALLOWLIST_PREFIXES = [
    'examples/fixtures/',
    'examples\\fixtures\\',
]

ALLOWLIST_FILES = [
    'SECURITY.md', 'QUICKSTART.md', 'README.md', 'README.zh-CN.md',
    'CHANGELOG.md', 'SKILL.md', 'task-report-schema.md',
    'check-public-safety.py',
]


def _get_tracked_files(target_path):
    """Return set of relative paths for git-tracked files.
    Uses git ls-files; falls back to os.walk if git unavailable."""
    try:
        result = subprocess.run(
            ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
            cwd=target_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            paths = result.stdout.split('\0')
            return [p for p in paths if p]
    except Exception:
        pass
    return None


def _is_in_forbidden_allowlist(rel_path):
    for prefix in FORBIDDEN_DIR_ALLOWLIST_PREFIXES:
        if rel_path.startswith(prefix):
            return True
    return False


def check_forbidden_tracked_dirs(target_path, tracked_files):
    """Check if any FORBIDDEN_TRACKED_DIRS appear in tracked paths."""
    has_fail = False
    if tracked_files is not None:
        for fpath in tracked_files:
            parts = fpath.replace('\\', '/').split('/')
            for d in parts:
                if d in FORBIDDEN_TRACKED_DIRS:
                    if not _is_in_forbidden_allowlist(fpath):
                        print(f"FAIL: Forbidden tracked directory found: {fpath}")
                        has_fail = True
                    break
    return has_fail


def check_forbidden_dirs_on_disk(target_path):
    """Walk disk to find FORBIDDEN_TRACKED_DIRS (recursive .agent-inbox etc.).
    Skip .git and known build dirs. Allowlist examples/fixtures paths."""
    has_fail = False
    for root, dirs, files in os.walk(target_path):
        # Skip .git
        if '.git' in dirs:
            dirs.remove('.git')

        rel_root = os.path.relpath(root, target_path)
        if rel_root == '.':
            rel_root = ''

        for d in dirs:
            if d in FORBIDDEN_TRACKED_DIRS:
                rel_path = os.path.join(rel_root, d).replace('\\', '/')
                if not _is_in_forbidden_allowlist(rel_path):
                    print(f"FAIL: Forbidden directory found on disk: {os.path.join(root, d)}")
                    has_fail = True
    return has_fail


def build_file_list(target_path):
    """Build (root, files) list for scanning. Skips forbidden dirs during walk."""
    files_to_check = []

    if os.path.isfile(target_path):
        files_to_check.append(
            (os.path.dirname(target_path) or '.', [os.path.basename(target_path)])
        )
    else:
        for root, dirs, files in os.walk(target_path):
            if '.git' in dirs:
                dirs.remove('.git')
            # Remove forbidden dirs from walk so their contents aren't scanned
            for fd in FORBIDDEN_TRACKED_DIRS:
                if fd in dirs:
                    dirs.remove(fd)
            files_to_check.append((root, files))

    return files_to_check


def check_safety(target_path):
    has_fail = False

    if not os.path.exists(target_path):
        print(f"FAIL: Target path does not exist: {target_path}")
        sys.exit(1)

    abs_target = os.path.abspath(target_path)

    # ---- Check 1: Forbidden tracked dirs (git ls-files) ----
    tracked = _get_tracked_files(abs_target)
    if tracked is not None:
        if check_forbidden_tracked_dirs(abs_target, tracked):
            has_fail = True

    # ---- Check 2: Forbidden dirs on disk (recursive) ----
    if check_forbidden_dirs_on_disk(abs_target):
        has_fail = True

    # ---- Check 3: Scan file contents ----
    files_to_check = build_file_list(abs_target)

    for root, files in files_to_check:
        for file in files:
            # Skip self and validator scripts
            if file in ('check-public-safety.py', 'validate-agent-inbox.py', 'gen_fixtures.py'):
                continue
            if file == '.git':
                continue

            filepath = os.path.join(root, file)
            basename = os.path.basename(filepath)

            # Block illegal file names
            if file in ('.env', 'repomix-output.xml', 'repomix-output.txt'):
                print(f"FAIL: Illegal file found: {filepath}")
                has_fail = True

            # Read file content
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                continue

            # ---- Secret patterns ----

            # GitHub tokens: github_pat_..., ghp_...
            if re.search(r'github_pat_[a-zA-Z0-9_]{20,}', content):
                print(f"FAIL: GitHub PAT found in {filepath}")
                has_fail = True

            if re.search(r'ghp_[a-zA-Z0-9]{36}', content):
                print(f"FAIL: GitHub personal access token found in {filepath}")
                has_fail = True

            # GitLab PAT: glpat-...
            if re.search(r'glpat-[a-zA-Z0-9\-_]{20,}', content):
                print(f"FAIL: GitLab PAT found in {filepath}")
                has_fail = True

            # Slack tokens: xox[baprs]-...
            if re.search(r'xox[baprs]-[a-zA-Z0-9\-]{10,}', content):
                print(f"FAIL: Slack token found in {filepath}")
                has_fail = True

            # npm tokens: npm_...
            if re.search(r'np' + r'm_[a-zA-Z0-9]{36}', content):
                print(f"FAIL: npm token found in {filepath}")
                has_fail = True

            # HuggingFace tokens: hf_...
            if re.search(r'hf_[a-zA-Z0-9]{20,}', content):
                print(f"FAIL: HuggingFace token found in {filepath}")
                has_fail = True

            # OpenAI keys: sk-(proj|ant|live|test)-...
            if re.search(r'sk-(proj|ant|live|test)-[a-zA-Z0-9\-_]{20,}', content):
                print(f"FAIL: OpenAI API key found in {filepath}")
                has_fail = True

            # Generic sk- (fallback for standard OpenAI keys)
            if re.search(r'sk-[a-zA-Z0-9]{20,}', content):
                print(f"FAIL: Generic sk- secret pattern found in {filepath}")
                has_fail = True

            # AWS access keys: AKIA...
            if re.search(r'AKIA[0-9A-Z]{16}', content):
                print(f"FAIL: AWS access key found in {filepath}")
                has_fail = True

            # Google API keys: AIza...
            if re.search(r'AIza[a-zA-Z0-9\-_]{35}', content):
                print(f"FAIL: Google API key found in {filepath}")
                has_fail = True

            # Generic secret assignment: api_key|secret|token|password = "..."
            generic_secret = re.compile(
                r'(api_key|secret|token|password)\s*=\s*["\'][^\'"]{8,}["\']',
                re.IGNORECASE,
            )
            if generic_secret.search(content):
                if basename not in ALLOWLIST_FILES:
                    print(f"FAIL: Hardcoded secret in {filepath}")
                    has_fail = True

            # ---- Private-path patterns ----

            # macOS/Linux: /Users/<real>/... and /home/<real>/...
            if re.search(r'/Users/(?!<name>|USERNAME|YOUR_USER)[A-Za-z]', content):
                print(f"FAIL: Real /Users/ path found in {filepath}")
                has_fail = True

            if re.search(r'/home/(?!<name>|USERNAME|YOUR_USER)[a-z]', content):
                print(f"FAIL: Real /home/ path found in {filepath}")
                has_fail = True

            # Windows: drive paths into known personal directories
            if re.search(
                r'[A-Z]:[\\/](Us' + r'ers|AI-Workspace|Workspace|OneDrive|Dropbox|iCloudDrive)[\\/]',
                content,
                re.IGNORECASE,
            ):
                # Allow <name>, USERNAME, YOUR_USER placeholders in Users
                if not re.search(
                    r'[A-Z]:[\\/]Us' + r'ers[\\/](<name>|USERNAME|YOUR_USER)[\\/]',
                    content,
                    re.IGNORECASE,
                ):
                    print(f"FAIL: Real Windows personal path found in {filepath}")
                    has_fail = True

            # F:/AI-Workspace (specific known project root pattern)
            if re.search(r'F:[\\/]AI' + '-Workspace', content, re.IGNORECASE):
                print(f"FAIL: Real F:/AI-Workspace path found in {filepath}")
                has_fail = True

            # C:\Users\ unless it is literally <name> / USERNAME / YOUR_USER
            if re.search(
                r'C:[\\/]Us' + r'ers[\\/](?!<name>|USERNAME|YOUR_USER)',
                content,
                re.IGNORECASE,
            ):
                print(f"FAIL: Real C:/Users/ path found in {filepath}")
                has_fail = True

    if has_fail:
        sys.exit(1)
    else:
        print("PASS: Public safety scan passed")
        sys.exit(0)


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    check_safety(target)
