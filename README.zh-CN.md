# Delegator Skill

[![Validation](https://github.com/windeternity/delegator-skill/actions/workflows/validation.yml/badge.svg)](https://github.com/windeternity/delegator-skill/actions/workflows/validation.yml)

[English](README.md)

**本地文件型 MOA 协调协议：边界内证据，coordinator 拍板。**

Delegator 是一套本地文件型 MOA 协调协议：多个 worker 在显式权限边界内产出结构化证据，coordinator 保留最终 `GO / PARTIAL / RED` 裁决权。当问题是语义风险、协议设计或候选 patch 取舍时，多个 worker 独立审同一个 decision surface，synthesis 比较证据而不是简单投票。同时也能帮你把 Codex 额度花在拆解、监督、验收和关键判断上，而不是消耗在长时间实现、测试、修错循环里。

多 Agent 编程最烦的不是模型不够多，而是人被迫当中转站：复制大段提示词、追谁在做什么、翻聊天记录找证据，还要担心某个 worker 超出任务范围，或者自称已经完成。

Delegator 把这个流程变成一套本地任务单：主力模型写任务，worker 只在授权范围内执行，完成后写回结构化结果报告，最后由主力模型查证据并给出 `GO / PARTIAL / RED`。

## 适合谁

如果你手里不止一个模型、Agent 或代码执行工具，Delegator 会比较适合你。它的目的是不让某一个最贵、最强的模型从头干到尾，而是让主力模型当总控，把明确、可边界化、可验收的任务分给其他 worker。

典型场景是：你可能用 Codex 或其他高可信 Agent 做拆解、监督和最终验收，同时把局部实现、测试、审查、文档整理等任务交给 GLM、MiniMax、DeepSeek、Qwen、本地模型等，并在OpenCode、Cline 类 Agent、Claude Code 3P模式、IDE Agent等工具中执行。

这些具体名称只是例子，不是推荐，也不是固定路由规则。模型质量、价格、工具权限和供应商稳定性都会变化，所以 Delegator 更看重当前项目里的 agent roster、权限边界和 smoke test 证据，而不是静态模型排名。

## 它解决什么痛点？

- **不用人肉中转。** 不再把同一段上下文反复复制给不同 Agent。
- **谁干什么很清楚。** 每个 worker 都有自己的任务单、权限边界和结果报告路径。
- **Worker 不能自说自话。** 结果报告只是证据，不是最终结论；worker 不能自我验收，也不能自己扩权。
- **主力模型少干体力活。** 它专注拆解、派活、查证据和拍板，把实现、测试、批量检查交给更便宜或更适合的 worker。
- **过程能复盘。** task、report、status、event、lock、verdict 都落在文件里，可查看、可 diff、可验证。
- **默认不放权。** 高风险操作默认关闭，任务单里的权限高于结果报告里的任何说法。

## 什么时候不要用？

很小的一次性修改不适合委托：写任务单、读结果报告和做验收本身也有成本。Delegator 更适合复杂、并行、需要证据审查，或可以把执行交给更便宜模型的任务。

当前版本会先运行硬路由门：预计直接完成少于 4 小时、没有真实并行流、也不需要特殊能力或独立高风险复核时，默认 `DIRECT`，不会读取 roster、模板或 inbox。只有满足门槛才进入完整协议；用户明确要求外部执行者的低风险非语义单任务可走无 inbox 的 `LITE`。

## 工作方式

```text
用户目标
  ↓
主力模型拆任务、写任务单
  ↓
Worker 只按自己的权限范围执行
  ↓
Worker 写回结构化结果报告
  ↓
主力模型查证据，给出 GO / PARTIAL / RED
```

```text
 主控                     .agent-inbox/                Worker
 ────                     ─────────────                ──────
 写任务单    ───────────► task-Reviewer-*.md
 读结果报告  ◄────────── report-Reviewer-*.md    ◄──── 读任务，在权限范围内
 给验收结论                                      │     工作，写结构化结果报告
                                                 │
 写任务单    ───────────► task-Implementer-*.md   │
 读结果报告  ◄────────── report-Implementer-*.md ◄────
 给出 GO / PARTIAL / RED
```

每个任务文件都是一张自包含的任务单：指定分给哪个 Agent、能做什么不能做什么、验收标准和结果报告路径。

```yaml
# .agent-inbox/task-Reviewer-guardrail-audit.md
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: demo-reviewer-guardrail-audit
agent_name: Reviewer
permission_scope:
  read_files: yes
  modify_source: no
  run_commands: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
validation_tier: no-test-needed
report_path: .agent-inbox/report-Reviewer-guardrail-audit.md
---
```

主力模型读回结果报告，检查证据，然后给出验收结论——不是凭感觉，而是按 7 个维度共 14 分来打分：范围、证据、验证、安全、可复现、冲突意识和提示词污染防护。

## 安装与冒烟测试

### 主控端（需要安装）

先 clone 或下载这个仓库，然后复制到 Codex skills 目录，命名为 `delegator`：

```powershell
git clone https://github.com/windeternity/delegator-skill.git
$dest = "$env:USERPROFILE\.codex\skills\agent-file-coordination"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Get-ChildItem .\delegator-skill -Force |
  Where-Object { $_.Name -notin @(".git", ".github", ".claude", ".codex", ".agent-inbox") } |
  Copy-Item -Destination $dest -Recurse -Force
```

macOS / Linux：

```bash
git clone https://github.com/windeternity/delegator-skill.git
mkdir -p ~/.codex/skills
rsync -a --delete \
  --exclude='.git' \
  --exclude='.github' \
  --exclude='.claude' \
  --exclude='.codex' \
  --exclude='.agent-inbox' \
  delegator-skill/ ~/.codex/skills/agent-file-coordination/
```

如果其他工具要承担主控职责，并且支持自定义 skill、prompt 或 context 目录，把 `SKILL.md`、`references/` 和 `docs/CODEX_FIRST_OPERATING_MODEL.md` 复制到对应目录即可。

### Worker 端（无需安装）

Worker 只需要任务文件和一行复制粘贴：

```text
读取 <task-file-path>。确认你是 <Agent Name>。只执行这一个任务，并按任务文件里的权限范围写回指定结果报告。额外动作需要用户另行授权。
```

也可以给 worker 提供 `references/worker-brief.md`，让它了解最基本的任务/报告格式。

### 冒烟测试

安装到 Codex 后，用中文或英文提问均可：

```text
Use the Delegator skill. Create a demo two-agent plan for a read-only review and a small implementation task. Use neutral agent names, write task files under .agent-inbox/, include permission scope and report trust fields, and give me only the one-line copy-paste instruction for each agent.
```

合格结果应包含：明确的 `Agent Name`、`Permission Scope`、`Workspace Mode`、`Guardrails`、`Acceptance Criteria`、`Report Path`、结果报告可信度字段，且不硬编码路径或厂商名称。

**首次触发 Skill** 时，Agent 会把 CAL 和 worker 默认配置写入安装目录内的 `LOCAL_ROSTER.md`，供各项目复用；项目名册仅作为显式覆盖。CAL-1/CAL-2 接受你人工转交的外部 worker；CAL-3 要求经过验证的可调用 CLI。见 [首次运行](docs/FIRST_RUN.md)。

### 验证

```powershell
python scripts/validate-agent-inbox.py examples/fixtures/valid     # 正常示例 — PASS
python scripts/validate-agent-inbox.py examples/two-agent-demo      # 演示 — PASS
python scripts/validate-agent-inbox.py examples/moa-review-demo     # MOA review 示例 — PASS
python scripts/validate-agent-inbox.py examples/moa-synthesis-demo  # MOA synthesis 示例 — PASS
python scripts/validate-agent-inbox.py examples/fixtures/invalid    # 错误示例 — 预期 FAIL
python scripts/check-public-safety.py .                             # 扫描机密/真实路径
# 注意：请在导出的公开包（或干净快照）上运行。私有上游检出包含本地协调状态
# （.agent-inbox、.learnings 等），即便导出包干净也会让公共安全扫描失败。
# 请在干净、隔离的包副本上运行扫描器，而非带本地状态的工作检出。
```

## 文档导航

**入门**
- [最小闭环](docs/MINIMAL_LOOP.md) — **第一次成功闭环先读这里，再看完整快速开始。** 五步、四个文件、无需聊天中转。
- [首次运行](docs/FIRST_RUN.md) — 从这里开始：首次委派时 Agent 会问你什么，以及不同自动化级别下要求有何不同
- [快速开始](docs/QUICKSTART.md) — 最小安装和冒烟测试
- [架构](docs/ARCHITECTURE.md) — 项目结构、文件角色与数据流
- [水合指南](docs/HYDRATION_GUIDE.md) — 首次使用模板水合流程

**深入了解**
- [定位](docs/POSITIONING.md) — 产品边界与 MOA-first 北极星
- [什么时候使用 AFC](docs/WHEN_TO_USE_AFC.md) — direct、LITE、FULL delegation 与 MOA 决策树
- [质量经济性](docs/QUALITY_ECONOMICS.md) — quality-adjusted coordination ROI
- [Benchmark Plan](docs/BENCHMARK_PLAN.md) — direct vs delegation vs MOA 证据记录模板
- [Codex-First 运行模型](docs/CODEX_FIRST_OPERATING_MODEL.md) — 推荐用法
- [缓存优化](docs/CACHE_HYGIENE.md) — 给主控和 worker 的 prompt 缓存建议
- [Worker Brief](references/worker-brief.md) — 给 worker 的轻量说明

**参考**
- [任务/结果报告 Schema](references/task-report-schema.md) — 任务、结果报告、名册、状态板、事件日志、worktree 锁和验收结论文件的 schema
- [MOA Coordination Modes](references/moa-coordination-modes.md) — `delegate_full`、`moa_review`、`moa_design`、`moa_patch`、`moa_synthesis`
- [MOA Synthesis Rubric](references/moa-synthesis-rubric.md) — 证据加权 synthesis 规则
- [Source Artifacts](references/source-artifacts.md) — 上游 PRD、spec、issue、report 输入
- [Assignment Quality Checklist](references/assignment-quality-checklist.md) — 派发前任务质量门
- [验收评分表](references/decision-rubric.md) — 14 分制验收 rubric
- [权限矩阵](references/action-permission-matrix.md) — Agent 动作默认允许/禁止矩阵
- [结果报告可信度与提示词污染](references/report-trust-and-prompt-injection.md) — 可信度级别与异常输入处理

## 范围与边界

Delegator 是一套任务协作协议，不是 Agent 运行时。它不自己执行代码，不绑定任何 worker 模型或厂商，不发布 benchmark。除非用户在当前项目里明确授权，否则不应自动提交、合并、删除分支、部署或暴露私有数据。保持 skill 仓库干净——不要提交生成的 inbox、worktree、结果报告、真实项目数据、`.env` 文件、日志或含私有信息的截图。

## 命名与兼容性

Delegator 是公开 Skill 名称。底层文件协议目前仍使用 `agent-file-coordination/*` schema namespace 和 `afc-*` 辅助脚本名称，以兼容现有模板、验证器、fixtures 和早期使用者。这些是稳定的协议标识，不代表另一个产品名。

## 许可证

[MIT](LICENSE)
