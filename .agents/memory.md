# 跨会话记忆

## 项目入口与真源

- 项目专属规则：`AGENTS.md`；人类入口：`README.md` 与 `docs/README.md`；开发与提交细则：`docs/项目工作流.md`、`docs/jj工作流.md`。
- 通用规则真源：个人工作流 `global/AGENTS.md`，不在本仓库复制；本机位置及自检命令见项目工作流文档。
- Python 版本约束和安装入口见 `pyproject.toml`；运行依赖来自 `requirements.txt`。测试使用 `unittest`。
- CLI 已分离为 `chaoxing_app/config.py`、`cli.py`、`jobs.py`，`main.py` 为薄入口；`api/` 已实施施工方案阶段 2-4（`api/answer.py` 已拆为 `api/answer/` 包），会话、视频、测验与签到仍集中在 `api/base.py`（复核时 1528 行，`study_video` 在 `:758`、`study_work` 在 `:898`）。
- 题库查询管道的回归在 `tests/test_answer_query.py`；其中两条仍待授权修复的缺陷以 `expectedFailure` 标记，修复后必须移除标记。

## 版本控制

- 已使用 Jujutsu colocated 模式，保留 Git 后端；禁止用 Git 写状态。`.jj/` 缺失时用 `jj git init --colocate` 恢复，而不是重建或改写历史。
- `.jj/` 不随 `git clone` 复制：本工作副本是重新 clone 的纯 Git 仓库，复核时重建了 colocated 元数据并 `jj bookmark track main@origin`；导入后 jj 推出的 change ID 与既有记录一致，说明历史未被改写。
- jj 二进制位于 `C:\Users\ppkun\AppData\Local\Microsoft\WinGet\Links\jj.exe`（0.45.1），本会话 PATH 未包含，需用绝对路径调用；仓库级 `user.name`/`user.email` 与 git 配置一致。
- 本地提交：`utlovuxp` CLI 重构、`npywrswo` Jujutsu 文档、`rrrklrkr` 工作流迁移、`nsuroxsp` API 施工方案、`tpyzokpu`/`txqptvwk`/`mylrlyor` API 阶段 2-4、`kzvmmpux` 记录更新、`ypvplmlw` 记录 main 位置、`nqowvmoz` 复核现状、`qvpsutuu` 补导入修复、`zmqolksk` 复核文档、`kuxywyko` 修复契约、`qwknwrqv` 查询管道、`lwnnruto` 缓存并发、`kvqxommw` Session、`oxzzmolx` 重做计数、`upsmutkl` 直播失败、`puwoqtnv` 判空顺序。
- `main` 现为 `ypvplmlw`（`94a205f`）并已推送到 `origin`；本轮修复只提交到本地 change，尚未推送；发布与提交是两步操作, 再次推送前先 `jj git fetch`。
- 后续版本位置以 `jj status`、`jj log` 为准，不使用本记录推断工作区是否干净。

## 授权与未实施方案

- API 施工方案保存在 `api重构施工方案.md`；阶段 2-4（纯函数与小模块、数据解析、题库拆包）已按明确授权实施，只做等价重构。
- 已授权并完成：方案第四节列出的缺陷修复（Session 重建、单题查询丢答案、缓存跨实例竞争、测验状态跨任务共享、直播失败未传播）与 `tiku` 判空顺序，各自独立 `fix` change。仍未授权：阶段 5-6 的会话、视频与测验流程拆分。
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
- 未覆盖：直播失败触发的真实重投与测验保存/提交策略需要可控测试课程，未在离线环境验证。
- 测试盲区（教训）：旧 103 项回归覆盖注册表与实例状态，从未调用 `query`/`query_all`；「`api/answer/` 各类 AST 与迁移前相同」的比对不含模块级导入，因此缺导入既没被测试也没被等价比对发现。
## 工作流迁移验证

- 真源 `check-agents.sh` 检查六份规则与导航文件通过，未发现事实与现状混入。
- 十六份 Markdown 的 UTF-8、LF、结尾换行和代码围栏检查通过，四十一个本地链接有效。
- 文档迁移后的源码和 wheel 构建、CLI 帮助启动通过；业务测试未重跑，因本次只改文档与镜像上下文忽略范围。
- 施工方案此前单独留在 `nsuroxsp`；`main` 已从 `kylyonvm` 快进到 `kzvmmpux` 并推送, 工作副本 `@` 为空提交, 不属于 `main`。
