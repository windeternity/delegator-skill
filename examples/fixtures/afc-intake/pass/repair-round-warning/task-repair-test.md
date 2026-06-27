---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: repair-round-test
agent_name: TestWorker
role: implementer
protocol_mode: task-only
coordinator_authority: no
routing_decision: DIRECT
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: yes
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: /nonexistent/afc-intake-fixture/__nonexistent_for_test__
  locked_files_or_areas: scripts/
completion_marker: done
validation_tier: none
report_path: /nonexistent/afc-intake-fixture/report-repair-test.md
created_at: 2026-06-24
---

# Test Task

This task is used to test repair-round budget counting.
