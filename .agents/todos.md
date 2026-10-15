# 待办

## API 施工方案

- [x] 阶段 2-4（纯函数与小模块、数据解析、题库拆包）已完成，等价重构与缺陷修复分开处理；验收：逐点行为比对、离线回归、仓库外安装 smoke 与文档同步，结果见 `memory.md`。
- [x] 阶段 4 拆包回归（`api/answer/core.py` 缺 `sub` 与 `CacheDAO` 导入）；change `qvpsutuu`。
- [x] 阶段 1 离线请求对照：`tests/fixtures/api_contracts/` 留存合成视频/测验样本，12 项签名/上报/保存/提交/重做对照在未改业务代码时通过；change `sumltmns`。真实脱敏响应/缓存留档仍有缺口，不把合成样本称为线上采集。
- [x] 阶段 5 交互解耦部分：唯一非重入锁迁入 `api/interaction.py`，logger、手动 provider 和视频共用；10 项交互回归及完整 150 项通过，源码分发与仓库外 wheel/sdist 验证通过；changes `lomtwkyw`、`xskzvptm`。不等于整个阶段 5 完成。
- [ ] 阶段 5 剩余会话管理拆分与阶段 6 视频/测验流程拆分；当前 `api/base.py` 仍为 1540 行单体（`study_video:772`、`study_work:906`），直播包装仍在；本轮不实施。验收：先定会话契约，保持请求参数、签名、保存/提交与重做次数一致，复跑离线对照和流程 smoke。
- [x] 第四节缺陷修复，每项一个独立 change，行为差异先记入施工方案「修复契约」，结果见同文「修复实施结果」：查询管道 `qwknwrqv`、缓存并发 `lwnnruto`、Session `kvqxommw`、重做计数 `oxzzmolx`、直播失败 `upsmutkl`、判空顺序 `puwoqtnv`；验收：新增 `test_answer_query.py`、`test_answer_cache.py`、`test_session.py`、`test_work_state.py` 与直播失败两例，离线回归 128 项通过，修复后离线探针逐项确认。
- [ ] 线上验收（需授权与可控测试课程）：直播失败章节重试的连带重跑、测验保存/提交与覆盖率门槛、Cookie 失效重新登录。本轮仅验证本地表单和返回语义，不证明服务端接受请求或确认任务点完成。
- [ ] 待定：共享 Session 被 4 个 worker 线程并发使用时的线程模型（线程隔离、加锁或维持现状）；验收：先给出并发契约与复现证据，再改代码。
- [x] 简易缺陷修复：缓存根节点不是 JSON 对象（`[1]`/`123`/`null`）不再抛 `AttributeError`，按内容损坏备份原文件并按空缓存继续、可正常重建；`notopen_action=ask` 增加启动 warning（行为仍与 retry 一致）。验收：新增 `test_non_object_json_is_treated_as_corrupt_without_raising` 与两条 ask/retry 提示回归，完整回归 153 项通过。
- [ ] 其余剩余缺陷见 `.agents/api重构施工方案.md`「剩余缺陷修整方案」：`TikuFallback` 反馈链感知、`run_live()` 全失败判定与重试粒度、共享 Session 线程模型、`_LOCKS` 生命周期与跨进程；均需先定契约或授权后再动代码。

## 文档中已明确的实现差异

- [ ] 是否实现真正的 `notopen_action=ask` 由后续需求决定（A 实现询问 / B 明确为 retry 别名 / C 维持现状+warning）；验收：用户授权行为变化后，实际 CLI 询问与取消/继续分支经过交互验证。当前仅增加启动提示，行为未变。

## 决策与授权边界

- [ ] 若后续任务需要新核心依赖、协议策略改变或线上副作用操作，集中提出具体选择；验收：记录明确决定、迁移范围与验证条件。在需要这些选择前不虚构审批制度。
- [ ] 真实提交、签到、进度上报或学习次数增加的验收需可控测试课程与场景授权；验收：明确副作用及可观察结果，不使用真实作业作为 smoke。
