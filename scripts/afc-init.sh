#!/usr/bin/env bash
# scripts/afc-init.sh
# Bootstrap a project-local .agent-inbox/ from the repository's
# templates/. POSIX shell features only, no external dependencies.
#
# Usage:
#   bash scripts/afc-init.sh [-p|--project-root PATH] [-d|--created-at YYYY-MM-DD] [-f|--force]
#
# Exit codes:
#   0  success
#   1  missing project root, missing templates, invalid date,
#      refuse-to-overwrite without --force, or other I/O error
#   2  invalid CLI usage

set -eu

usage() {
    cat <<'EOF'
usage: afc-init.sh [-p|--project-root PATH] [-d|--created-at YYYY-MM-DD] [-f|--force] [-h|--help]

Options:
  -p, --project-root PATH   Project root to bootstrap (default: current directory).
  -d, --created-at DATE     Date for updated_at and event created_at (default: today, local).
  -f, --force               Overwrite existing .agent-inbox files.
  -h, --help                Show this help.
EOF
}

# --- Argument parsing ---
PROJECT_ROOT="."
CREATED_AT=""
FORCE=0

while [ $# -gt 0 ]; do
    case "$1" in
        -p|--project-root)
            if [ $# -lt 2 ]; then
                echo "error: --project-root requires a value" >&2
                usage >&2
                exit 2
            fi
            PROJECT_ROOT="$2"
            shift 2
            ;;
        --project-root=*)
            PROJECT_ROOT="${1#*=}"
            shift
            ;;
        -d|--created-at)
            if [ $# -lt 2 ]; then
                echo "error: --created-at requires a value" >&2
                usage >&2
                exit 2
            fi
            CREATED_AT="$2"
            shift 2
            ;;
        --created-at=*)
            CREATED_AT="${1#*=}"
            shift
            ;;
        -f|--force)
            FORCE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "error: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            echo "error: unexpected positional argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

# --- 1. Resolve project root ---
if [ ! -e "$PROJECT_ROOT" ]; then
    echo "error: project root does not exist: $PROJECT_ROOT" >&2
    exit 1
fi
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"

# --- 2. Resolve templates directory (sibling of scripts/) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATES_DIR="$(cd "$SCRIPT_DIR/../templates" && pwd)"
if [ ! -d "$TEMPLATES_DIR" ]; then
    echo "error: templates directory does not exist: $TEMPLATES_DIR" >&2
    exit 1
fi

# --- 3. Validate / default the created date ---
if [ -z "$CREATED_AT" ]; then
    CREATED_AT="$(date +%Y-%m-%d)"
elif ! printf '%s' "$CREATED_AT" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
    echo "error: invalid --created-at format: $CREATED_AT (expected YYYY-MM-DD)" >&2
    exit 1
fi

# --- 4. Refuse to overwrite existing files unless --force ---
INBOX_DIR="$PROJECT_ROOT/.agent-inbox"
EXISTING=""
for name in AGENT_ROSTER.md STATUS.md WORKTREE_LOCKS.md events.jsonl; do
    p="$INBOX_DIR/$name"
    if [ -e "$p" ]; then
        EXISTING="$EXISTING $p"
    fi
done
if [ -n "$EXISTING" ] && [ "$FORCE" -ne 1 ]; then
    echo "error: refusing to overwrite existing .agent-inbox files:$EXISTING. Use --force to overwrite." >&2
    exit 1
fi

# --- 5. Ensure .agent-inbox exists ---
mkdir -p "$INBOX_DIR"

# --- 6. Copy templates with date substitution ---
copy_template() {
    src="$1"
    dst="$2"
    if [ ! -f "$src" ]; then
        echo "error: template not found: $src" >&2
        exit 1
    fi
    awk -v date="$CREATED_AT" '{ gsub(/<YYYY-MM-DD>/, date); print }' "$src" > "$dst"
}

copy_template "$TEMPLATES_DIR/TEMPLATE_ROSTER.md"        "$INBOX_DIR/AGENT_ROSTER.md"
copy_template "$TEMPLATES_DIR/TEMPLATE_STATUS_BOARD.md"  "$INBOX_DIR/STATUS.md"
copy_template "$TEMPLATES_DIR/TEMPLATE_WORKTREE_LOCKS.md" "$INBOX_DIR/WORKTREE_LOCKS.md"

# --- 7. Write events.jsonl with one ROSTER_UPDATED event ---
# Use awk for safe JSON assembly (printf handles backslashes/quotes cleanly).
awk -v date="$CREATED_AT" 'BEGIN {
    printf("{\"schema\":\"agent-file-coordination/event\",\"schema_version\":\"0.1.0\",");
    printf("\"event_id\":\"evt-001\",\"event_type\":\"ROSTER_UPDATED\",");
    printf("\"created_at\":\"%s\",", date);
    printf("\"summary\":\"Created project agent inbox from template hydration.\"}\n");
}' > "$INBOX_DIR/events.jsonl"

echo "Wrote $INBOX_DIR"
echo "  AGENT_ROSTER.md"
echo "  STATUS.md"
echo "  WORKTREE_LOCKS.md"
echo "  events.jsonl"
exit 0
