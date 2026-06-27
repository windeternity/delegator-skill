#!/usr/bin/env pwsh
# scripts/afc-init.ps1
# Bootstrap a project-local .agent-inbox/ from the repository's
# templates/. Stdlib PowerShell only, no external dependencies.
#
# Usage:
#   pwsh -File scripts/afc-init.ps1 [-ProjectRoot <path>] [-CreatedAt YYYY-MM-DD] [-Force]
#
# Exit codes:
#   0  success
#   1  missing project root, missing templates, invalid date,
#      refuse-to-overwrite without -Force, or other I/O error
#   2  invalid CLI usage (handled by PowerShell's parameter binder)

[CmdletBinding()]
param(
    [string]$ProjectRoot = ".",
    [string]$CreatedAt = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# --- 1. Resolve project root ---
if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    Write-Error "project root does not exist: $ProjectRoot"
    exit 1
}
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).ProviderPath

# --- 2. Resolve templates directory (sibling of scripts/) ---
$ScriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($ScriptDir)) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrEmpty($ScriptDir)) {
    Write-Error "could not determine script directory"
    exit 1
}
$TemplatesDir = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".." "templates"))
if (-not (Test-Path -LiteralPath $TemplatesDir)) {
    Write-Error "templates directory does not exist: $TemplatesDir"
    exit 1
}

# --- 3. Validate / default the created date ---
if ([string]::IsNullOrEmpty($CreatedAt)) {
    $CreatedAt = (Get-Date).ToString("yyyy-MM-dd")
} elseif ($CreatedAt -notmatch '^\d{4}-\d{2}-\d{2}$') {
    Write-Error "invalid --CreatedAt format: $CreatedAt (expected YYYY-MM-DD)"
    exit 1
}

# --- 4. Refuse to overwrite existing files unless -Force ---
$InboxDir = Join-Path $ProjectRoot ".agent-inbox"
$Targets = @("AGENT_ROSTER.md", "STATUS.md", "WORKTREE_LOCKS.md", "events.jsonl")
$Existing = @()
foreach ($name in $Targets) {
    $p = Join-Path $InboxDir $name
    if (Test-Path -LiteralPath $p) {
        $Existing += $p
    }
}
if (($Existing.Count -gt 0) -and -not $Force.IsPresent) {
    Write-Error ("refusing to overwrite existing .agent-inbox files: " + ($Existing -join ", ") + ". Use -Force to overwrite.")
    exit 1
}

# --- 5. Ensure .agent-inbox exists ---
if (-not (Test-Path -LiteralPath $InboxDir)) {
    New-Item -ItemType Directory -Path $InboxDir -Force | Out-Null
}

# --- 6. Copy templates with date substitution ---
function Copy-AfcTemplate {
    param(
        [Parameter(Mandatory = $true)][string]$TemplateName,
        [Parameter(Mandatory = $true)][string]$TargetName
    )
    $src = Join-Path $TemplatesDir $TemplateName
    $dst = Join-Path $InboxDir $TargetName
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Error "template not found: $src"
        exit 1
    }
    $content = Get-Content -LiteralPath $src -Raw
    $content = $content -replace "<YYYY-MM-DD>", $CreatedAt
    Set-Content -LiteralPath $dst -Value $content -NoNewline -Encoding utf8
}

Copy-AfcTemplate "TEMPLATE_ROSTER.md"      "AGENT_ROSTER.md"
Copy-AfcTemplate "TEMPLATE_STATUS_BOARD.md" "STATUS.md"
Copy-AfcTemplate "TEMPLATE_WORKTREE_LOCKS.md" "WORKTREE_LOCKS.md"

# --- 7. Write events.jsonl with one ROSTER_UPDATED event ---
$event = [ordered]@{
    schema         = "agent-file-coordination/event"
    schema_version = "0.1.0"
    event_id       = "evt-001"
    event_type     = "ROSTER_UPDATED"
    created_at     = $CreatedAt
    summary        = "Created project agent inbox from template hydration."
}
$eventJson = $event | ConvertTo-Json -Compress
$eventsPath = Join-Path $InboxDir "events.jsonl"
Set-Content -LiteralPath $eventsPath -Value ($eventJson + [Environment]::NewLine) -NoNewline -Encoding utf8

Write-Host "Wrote $InboxDir"
Write-Host "  AGENT_ROSTER.md"
Write-Host "  STATUS.md"
Write-Host "  WORKTREE_LOCKS.md"
Write-Host "  events.jsonl"
exit 0
