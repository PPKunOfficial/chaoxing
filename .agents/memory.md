# 跨会话记忆

## 项目入口与真源

- 项目专属规则：`AGENTS.md`；人类入口：`README.md` 与 `docs/README.md`；开发与提交细则：`docs/项目工作流.md`、`docs/jj工作流.md`。
- 通用规则真源：个人工作流 `global/AGENTS.md`，不在本仓库复制；本机位置及自检命令见项目工作流文档。
- Python 版本约束和安装入口见 `pyproject.toml`；运行依赖来自 `requirements.txt`。测试使用 `unittest`。
- CLI 已分离为 `chaoxing_app/config.py`、`cli.py`、`jobs.py`；`api/` 已完成阶段 2-4 和阶段 5 的交互解耦部分（新增 `api/interaction.py`）。会话、视频、测验与签到仍集中在 `api/base.py`（1540 行，`study_video:772`、`study_work:906`），整个阶段 5 尚未完成。
- 题库查询管道的回归在 `tests/test_answer_query.py`；原先标记的两条 `expectedFailure` 已随修复移除，当前无 `expectedFailure`。

## 版本控制

- 已使用 Jujutsu colocated 模式，保留 Git 后端；禁止用 Git 写状态。`.jj/` 缺失时用 `jj git init --colocate` 恢复，而不是重建或改写历史。
- `.jj/` 不随 `git clone` 复制：本工作副本是重新 clone 的纯 Git 仓库，复核时重建了 colocated 元数据并 `jj bookmark track main@origin`；导入后 jj 推出的 change ID 与既有记录一致，说明历史未被改写。
- 当前 macOS 会话使用 `/opt/homebrew/bin/jj`（0.46.0）和 `$HOME/.local/bin/uv`（0.8.22），PATH 未包含它们；运行解释器为项目 `.venv/bin/python`（3.13.12）。此前 Windows 会话的 jj 在 WinGet Links 目录（0.45.1），不据此推断本机路径。
- 本地提交：`utlovuxp` CLI 重构、`npywrswo` Jujutsu 文档、`rrrklrkr` 工作流迁移、`nsuroxsp` API 施工方案、`tpyzokpu`/`txqptvwk`/`mylrlyor` API 阶段 2-4、`kzvmmpux` 记录更新、`ypvplmlw` 记录 main 位置、`nqowvmoz` 复核现状、`qvpsutuu` 补导入修复、`zmqolksk` 复核文档、`kuxywyko` 修复契约、`qwknwrqv` 查询管道、`lwnnruto` 缓存并发、`kvqxommw` Session、`oxzzmolx` 重做计数、`upsmutkl` 直播失败、`puwoqtnv` 判空顺序、`worptzsz` 修复实施结果、`nlqpxmmx` 复查结论。
- 本轮已同步 `main`/`origin/main` 到 `nyzpnzul`（`56484f37`）。本地新增 `sumltmns` 离线对照、`lomtwkyw` 源码分发、`xskzvptm` 交互解耦；未推送，也未移动已发布 main。发布与提交是两步操作，再次推送前先 `jj git fetch`。
- 此前 Windows 会话直连 GitHub 被重置，经 `127.0.0.1:7897` 代理成功；当前 macOS 已成功 fetch，不默认继承该机器的代理配置。凭据、代理及二进制位置按当前环境核对。
- 后续版本位置以 `jj status`、`jj log` 为准，不使用本记录推断工作区是否干净。

## 授权与未实施方案

- API 施工方案保存在 `api重构施工方案.md`；阶段 2-4（纯函数与小模块、数据解析、题库拆包）已按明确授权实施，只做等价重构。
- 第四节缺陷及 `tiku` 判空顺序已按授权独立修复；本轮另获批准并完成离线请求对照与阶段 5 交互解耦。会话管理、Session 线程模型、视频/测验拆分、直播包装合并及其他既有缺陷不在本轮授权范围。
- 线上副作用验收仍需明确场景授权与可控测试课程。

## 已观察验证及限制

- 前次 CLI 重构的 Python 3.13 离线回归为 35 项通过；源码、模块与安装命令帮助通过。
- wheel 仓库外安装与离线任务 smoke 通过：文档任务执行、已完成章节跳过、工作线程退出、进度格式恢复与字体映射加载。
- 阶段 2-4 的等价比对：answer_check 与 cookies 在 50 项输入上与原实现逐点无差异；cipher 五个固定输入的密文与重构前一致；decode 与作答记录解析的取值和异常边界一致；`api/answer/` 各类的 AST 与迁移前完全相同，provider 名称顺序、实例默认值与构造分支逐项比对无差异。
- 阶段 2-4 的离线回归为 103 项通过；源码、模块与安装命令帮助通过；`uv build` 成功且 wheel 含 `api/answer` 子包；wheel 在仓库外目录解包后 `chaoxing_app --help` 与题库装配 smoke 通过。
- 上述离线结果与 API 只读探针都不覆盖真实登录、题库服务、验证码、直播、作答提交与 Docker/Windows 打包。
- 复核（阶段 2-4 完成后）：按 LF 归一化工作树后重跑离线回归仍为 103 项通过；`jj status` 干净、`@` 为空提交；本次只读取代码与文档，未编辑业务代码。
- API 只读探针复现 Session 重建、单题查询丢答案与反馈分支未绑定 `cache_dao`；原始输出与推断边界见施工方案。
- 复核发现阶段 4 拆包引入回归：`api/answer/core.py` 缺 `sub` 与 `CacheDAO` 两个导入，题库启用时 `query`/`query_all` 抛 `NameError`，经 `jobs.py` 线程包装会中断整个学习流程。已在 change `qvpsutuu` 修复并新增 `tests/test_answer_query.py`。
- 并发探针复现缓存跨实例丢更新：两个 `CacheDAO` 实例各写 200 条，落盘 6 条、丢 394 条，并伴随 `WinError 5`/`Permission denied`；已修复（按文件共享锁），修复后同一探针为 400/400。
- 缺陷修复后的离线验收（不联网、无 monkeypatch）：单题查询 `'B'`、批量 `['B']`、反馈模式单题 `'B'`、`session identity preserved: True`、`session header preserved: 1`、缓存 400/400、`tiku=None` 时 `study_work` 返回 SUCCESS、客户端不再持有 `rollback_times`。
- 修复后的离线回归为 128 项通过（无 `expectedFailure`），新增 `test_answer_cache.py`、`test_session.py`、`test_work_state.py`；三种 CLI 入口帮助、`compileall` 通过。
- 未覆盖：直播失败后的真实重投，以及测验保存/提交与覆盖率门槛的线上端到端策略；本轮离线对照仅验证本地组表与轮次，不验证服务器接受请求。可控测试课程与场景授权仍是线上验收前提。
- 测试盲区（教训）：旧 103 项回归覆盖注册表与实例状态，从未调用 `query`/`query_all`；「`api/answer/` 各类 AST 与迁移前相同」的比对不含模块级导入，因此缺导入既没被测试也没被等价比对发现。
## 工作流迁移验证

- 真源 `check-agents.sh` 检查六份规则与导航文件通过，未发现事实与现状混入。
- 十六份 Markdown 的 UTF-8、LF、结尾换行和代码围栏检查通过，四十一个本地链接有效。
- 文档迁移后的源码和 wheel 构建、CLI 帮助启动通过；业务测试未重跑，因本次只改文档与镜像上下文忽略范围。
- 施工方案此前单独留在 `nsuroxsp`；`main` 已从 `kylyonvm` 快进到 `kzvmmpux` 并推送, 工作副本 `@` 为空提交, 不属于 `main`。

## 本轮离线对照与交互解耦验证

- 阶段 1 对照产物在 `tests/fixtures/api_contracts/` 与 `tests/test_api_contracts.py`：固定视频签名、首次/后续上报参数及五类题型的保存/提交/重做表单。新增 12 项在未改业务代码时通过，完整回归从 128 项增至 140 项；样本均为合成数据，不冒充真实响应采集。
- `tests/test_interaction.py` 新增 10 项：唯一非重入锁、多实例单题/批量输入互斥、输入异常释放、1000 条日志缓冲上限与顺序、下一条日志触发冲刷、视频进度关闭/恢复和异常清理；独立进程导入边界通过。最终完整回归 150 项通过，无 `expectedFailure`。
- 三种 CLI 帮助入口通过（仅入口名及 usage 自动换行不同）、compileall 通过；sdist/wheel 构建通过，包含 `api/interaction.py`。发现并补齐源码分发遗漏的测试包入口，sdist 解包后从仓库外运行完整 150 项通过。
- wheel 通过 `uv pip install --target <scratch>` 安装，复用已安装的项目依赖；仓库外确认业务模块来自 wheel、测试/样本来自 sdist，运行新增 22 项流程、字体资源加载及模块/安装命令帮助均通过。这不是全新环境依赖安装或 Windows/Docker 验收。
- 真源 `check-agents.sh` 六文件检查通过；本轮没有修改 `process.py`、Session 线程模型或平台协议策略，没有执行真实登录、提交、签到、进度上报或学习次数增加。
- 验证日志与包在 session scratch：`contracts-baseline.log`、`gate-a-tests.log`、`final-tests.log`、`build-final.log`、`wheel-smoke-final.log`、`sdist-tests-final.log`、`dist-final/`。宿主生成的批准计划保留在工作区，不纳入上述工程 change。

## 简易缺陷修复与剩余项

- 缓存根节点不是 JSON 对象（`[1]`/`"text"`/`123`/`null`）时 `get_cache` 曾抛 `AttributeError`；现于 `_read_cache_once` 校验 `isinstance(data, dict)`，不符合按「内容损坏」备份后按空缓存继续，写入可重建。离线实测：`get_cache -> None`、备份生成、`add_cache` 后文件为 `{'q': 'A'}`。回归 `tests/test_answer_cache.py::test_non_object_json_is_treated_as_corrupt_without_raising`。
- `notopen_action=ask` 仍在 `JobProcessor.__init__` 记录一条 warning 后与 `retry` 同分支，**行为未变**；`tests/test_job_processor.py` 覆盖 ask 提示一次、retry/continue 不提示。真正询问属行为变更，仍待授权。
- 完整回归从 150 项增至 **153 项通过**；`check-agents.sh`、Markdown 格式与本地链接、compileall 通过。本轮未执行线上协议、Docker、Windows/PyInstaller 或远端 CI。
- 剩余缺陷的契约、选项与验证方式已写入 `.agents/api重构施工方案.md`「剩余缺陷修整方案」（TikuFallback 反馈链、`run_live()` 全失败判定与重试粒度、Session 线程模型、`_LOCKS` 生命周期、线上验收、阶段 5 剩余与阶段 6）；未授权前不改代码。
- 事实修正：本机 `main` 已推送到 `origin/main`（`41234e28`，含 `sumltmns`/`lomtwkyw`/`xskzvptm` 三个 change）。
