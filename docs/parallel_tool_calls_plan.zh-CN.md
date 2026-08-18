# 并行只读工具调用修正计划

## 背景

分支 `feat/parallel-readonly-tools` 的目标是让彼此独立的只读工具并行执行，
同时继续串行执行会推进环境或修改共享状态的工具。当前实现通过
`@parallel` 和 `@readonly` 标记工具，并把 Claude Code 工具桥原有的全局
串行锁下沉为 `Toolkit` 中的 reader/exclusive 条件变量。

代码审查发现，当前实现可以并行执行 reader，但还没有完整定义排队、
取消和 Dashboard 任务切换的关系。最危险的情况是：reader 正在执行、
机器人动作正在等待时，Dashboard 中断只检查当前 active exclusive
operation，因此会立即返回；reader 结束后，等待中的机器人动作仍可能启动。

本计划以最小改动修正这一问题，不重写 planner，也不让 Dashboard 自己承担
工具调度职责。

## DeepSeek Harness 的参考实现

参考代码为官方 `deepseek-ai/deepseek-harness` 仓库 commit
`47f943859bef60e4160492346772ded9b24f765a`（2026-08-13）。其核心设计见：

- [并行工具调用设计说明](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/feature/2026-07-10-parallel-tool-call-execution.md)
- [Agent Loop 调度实现](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/agent-loop/src/tool-calls.ts)
- [取消与并发测试](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/agent-loop/tests/tool-calls.spec.ts)

DeepSeek Harness 在完整 assistant message 到达后，一次取得其中所有 sibling
tool calls，并按模型顺序进行以下调度：

```text
parallel read A
parallel read B
exclusive write
parallel read C

=> [read A, read B]
=> [write]
=> [read C]
```

连续的并行安全调用组成一个并行组，exclusive 调用形成 barrier。取消由当前
turn 共用的 `AbortSignal` 传播：abort 后停止启动后续调用，等待已经启动的
调用收敛，并为未启动调用记录 `ABORTED_BEFORE_DISPATCH`。Web UI 只请求取消，
等待 Agent Loop 发布 `turn/end(aborted)`，不直接管理工具锁。

RPent 不能直接复制该实现。RPent 的 API planner 能看到较多模型节点信息，
但 Claude Code 和 Codex 的 Agent Loop 位于外部 SDK 中；RPent 的 MCP bridge
只会逐个收到工具回调，无法可靠获得完整 sibling batch、模型内顺序或 SDK
内部的 turn `AbortSignal`。因此，本次仍在 `Toolkit` 统一执行安全约束，但吸收
DeepSeek 的三个原则：显式 opt-in、exclusive barrier、取消后停止启动并 drain。

## 目标

1. 显式标记的只读工具可以并行执行。
2. 会推进环境或修改共享状态的工具保持独占。
3. exclusive 工具按进入 RPent 工具桥的顺序执行，reader 不跨越已经排队的
   exclusive barrier。
4. 中断后不再启动任何属于旧 planner turn 的等待工具。
5. Dashboard 在报告中断或切换任务完成前，旧 TaskRun 的工具已经完全停稳。
6. 普通 Dashboard Esc 中断成功后，可以继续处理排队的用户消息。
7. 任务替换、planner timeout 和 session 关闭后，旧 Toolkit 不再接受调用。

## 非目标

- 不在本次接管 Claude Code、Codex 或 PydanticAI 的 Agent Loop。
- 不尝试从多个 MCP 请求反推完整 assistant tool-call batch。
- 不并行执行写操作，即使它们看起来访问不同文件或不同资源。
- 不增加资源级读写声明或通用事务系统。
- 不改变模型可见的工具 schema。
- 不运行 GPU 实验；本次验证全部是 CPU-only 并发和控制流测试。

## 设计方案

### 1. 保留显式工具策略

继续使用：

```python
@parallel
@readonly
def view_env_state(...):
    ...
```

`@readonly` 只表示工具不推进环境，因此执行后不捕获新环境状态；`@parallel`
额外承诺该 handler 及其访问的共享数据可以与其他 parallel reader 同时执行。

注册工具时强制验证：`@parallel` 必须同时具有 `@readonly`。原因是调度安全不能
依赖文档约定；漏写 `@readonly` 时必须尽早失败，不能把可能移动机器人的工具
放进 reader 组。

本次只给已经确认只读取稳定快照或普通文件的工具添加 `@parallel`：

- `view_env_state`
- `view_camera_meta`
- `back_project`
- `read_text_file`
- `list_dir`

`segment`、`write_text_file`、`finish` 和所有机器人动作保持 exclusive。

### 2. 用 FIFO admission queue 替换计数器竞争

`Toolkit.execute_tool()` 在等待执行资格之前，先创建并登记一个 operation。每个
operation 至少记录：

- 单调递增的 admission sequence；
- parallel 或 exclusive 策略；
- queued、running、done 或 cancelled 状态；
- active exclusive 动作使用的 `cancel_event`；
- 所有调用使用的 `done_event`。

调度规则：

1. 队首连续的 parallel operations 可以共同进入 running。
2. exclusive operation 只有在它前面没有 operation，且没有 running reader 或
   exclusive operation 时才可启动。
3. 已经有 exclusive operation 排队后，后来 reader 不得越过它。
4. exclusive operation 一次只运行一个。

这样既保留 reader 并行，也为 writer 提供 barrier 和公平性。这里保证的是
“进入 RPent 工具桥的顺序”；由于外部 SDK 不提供完整 batch，不能声称恢复模型
assistant message 中更强的全局顺序。

### 3. 区分未启动取消和运行中取消

取消等待中的 operation：

- 从队列中移除或标记为 cancelled；
- 不调用 handler；
- 不捕获环境状态；
- 返回结构化 `tool_cancelled` 结果。

取消已经运行的 exclusive operation：

- 设置其 `cancel_event`；
- 由 primitive 在现有 `raise_if_cancelled()` 安全边界退出；
- 因为动作可能已经推进环境，仍捕获中断后的最终环境状态。

已经运行的 parallel reader 不要求强制终止，但取消流程必须等待它返回。它只
读取旧 TaskRun 的快照；在它退出前不能 reset state、关闭 Toolkit 或停止环境
runtime。

### 4. 让取消同时充当临时 admission gate

重新定义 `cancel_active_and_wait()`：

1. 原子地停止接受新 operation；
2. 取消所有 queued operation；
3. 请求取消 active exclusive operation；
4. 等待全部已登记 operation 到达 done；
5. 返回时仍保持 Toolkit 暂停。

新增 `resume_operations()`，只在同一 TaskRun 的普通中断成功后重新开放。
该方法只能在 Toolkit 已经 idle 时调用。

保持暂停直到 planner backend 完成 interrupt 很重要。否则会出现一个竞态窗口：
Toolkit 刚 drain 完成，Claude/Codex 旧 turn 又发来一个 MCP 调用，而 backend
interrupt 尚未生效。让 `cancel_active_and_wait()` 返回后继续保持 gate 关闭，
可以拒绝这个迟到调用。

取消和 resume 都应幂等，方便 session cleanup 在不同 `finally` 路径重复调用。

### 5. Dashboard 中断时序

修改 `DashboardPlannerControl` 的普通 Esc 路径：

```text
Dashboard 接受 interrupt
  -> Toolkit cancel + drain，并保持暂停
  -> planner driver interrupt
  -> interrupt 成功
  -> Toolkit resume
  -> Dashboard 标记 interrupt 完成
  -> flush 排队消息
```

为什么先 drain Toolkit，再 interrupt planner：机器人 primitive 只能在自身的安全
边界协作退出；外部 SDK 的 task cancellation 不能终止已经进入 Python worker
thread 的 handler。Toolkit 必须先取得控制权并阻止新动作，随后再终止产生这些
调用的旧 planner turn。

如果 `driver.interrupt()` 失败，不调用 `resume_operations()`。这时不能确认旧 turn
已停止，重新开放 Toolkit 可能允许它继续发出机器人动作。Dashboard 记录错误，
用户仍可通过任务替换结束旧 TaskRun。

### 6. Dashboard 任务替换和关闭

任务替换路径执行：

```text
Toolkit cancel + drain，并保持暂停
  -> planner driver interrupt
  -> seal 旧 interaction
  -> planner solve 返回
  -> toolkit.close()
  -> 停止旧 task runtime
  -> 初始化新 TaskRun
```

该路径不调用 `resume_operations()`。这样 `toolkit.close()`、episode video flush 和
旧环境 daemon 停止时，不会仍有 reader 或动作线程访问旧状态。

adapter/session 正常关闭、非 Dashboard planner timeout 也只 cancel + drain，
不 resume。

### 7. 终端交互模式

Claude Code 的终端交互模式也会通过 `driver.interrupt()` 中断当前 turn。并行功能
启用后，它具有与 Dashboard 相同的迟到工具风险。因此复用相同顺序：

```text
Toolkit cancel + drain -> driver interrupt -> Toolkit resume -> 提交新输入
```

终端退出则不 resume。API planner 当前只在工具边界接收终端输入，没有同样的
运行中工具 interrupt 路径，本次不为它增加额外状态机。

## 预计修改范围

### `rpent/tools/toolkit.py`

- operation 增加 queue/admission 状态；
- 实现 FIFO reader/exclusive barrier；
- 验证 `parallel => readonly`；
- 取消 queued operations；
- drain 所有 started operations；
- 增加幂等 `resume_operations()`。

### `rpent/dashboard/planner_control.py`

- 接收 Toolkit resume callback；
- 普通 Esc 成功后 resume，再 flush 消息；
- task replacement、失败和 close 路径不 resume。

### `rpent/planner/claude_code.py`

- Dashboard adapter 传入 resume callback；
- terminal adapter 在 interrupt 周围复用 cancel/drain/resume 顺序；
- 保持 MCP callback 自身无工具名硬编码。

### `rpent/planner/api_loop.py` 和 `rpent/planner/codex.py`

- 只做 Dashboard control 构造参数的机械传递；
- timeout 和 close 继续保持取消后不 resume。

### 文档

- 英文和中文 `development/add_primitive.rst` 明确区分 `readonly` 与
  `parallel-safe`；
- 说明 parallel 工具必须只读取并发安全的稳定状态。

## 测试计划

新增 CPU-only 单元测试，使用 `threading.Event` 或等价同步原语，不依赖不稳定的
固定 sleep 判断并发正确性。

### Toolkit 调度

1. 两个 parallel reader 在任意一个完成前均可启动。
2. exclusive operation 不与 reader 重叠。
3. 两个 exclusive operations 按 admission sequence 执行。
4. exclusive operation 排队后，后来 reader 不得插队。
5. `@readonly` 但没有 `@parallel` 的工具仍保持 exclusive。
6. `@parallel` 没有 `@readonly` 时注册失败。

### 取消和收敛

1. active reader + queued action：取消后 action handler 永不启动。
2. active action + queued action：两者都被取消，第二个 handler 永不启动。
3. active action 在安全边界抛出 `ToolCancelled` 后仍捕获最终状态。
4. cancel 等待 active reader 返回后才完成。
5. cancel 返回后到 resume 前到达的调用立即得到 `tool_cancelled`。
6. resume 后的新调用可以正常执行。
7. 重复 cancel、重复 cleanup 和合法 resume 不造成计数负数、死锁或遗漏通知。

### Dashboard 控制流

使用 fake interaction、driver 和 Toolkit callbacks 验证调用顺序：

1. 普通 Esc：cancel/drain -> driver interrupt -> resume -> flush。
2. task replacement：cancel/drain -> driver interrupt，不 resume。
3. driver interrupt 失败：不 resume，并记录 interaction error。
4. adapter close：drain 完成后 seal interaction。
5. 排队消息只在成功 resume 后提交。

### Claude 终端交互

1. steering 输入在旧 Toolkit drain 和 backend interrupt 后才提交。
2. `/quit` 或 EOF 取消并 drain，但不 resume。

## 验证命令

实现后在本地 worktree 运行：

```bash
git diff --check
ruff check rpent robots
python -m compileall -q rpent robots
pytest -q <新增测试路径>
```

若仓库届时仍未配置 pytest 测试目录，则在本分支新增最小测试目录和必要配置，
不引入与并行调度无关的测试框架改造。

本次不需要远程 GPU、模型 API 或真实机器人验证。若后续需要做端到端 Dashboard
验证，应使用 mock primitive 或模拟环境，先验证中断后没有旧 action 启动，再考虑
真实环境实验。

## 完成标准

只有同时满足以下条件才认为修改完成：

1. 已确认的 parallel reader 可以重叠执行。
2. 所有 exclusive 工具继续形成 barrier。
3. Dashboard 或终端中断后，旧 turn 的 queued action 不会启动。
4. TaskRun cleanup 前 Toolkit 已完全 idle。
5. 普通 Dashboard 中断后仍可继续发送消息和执行新工具。
6. 上述行为由确定性的 CPU-only 测试覆盖。
7. 英文和中文 primitive 开发文档与实现一致。
