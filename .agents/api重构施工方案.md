# API Pythonic 重构施工方案

## 状态与范围

- 状态：阶段 2-4（纯函数与小模块、数据解析、题库拆包）已实施；阶段 5-6 与第四节缺陷修复尚未执行。
- 授权范围：只授权等价重构；缺陷修复仍需单独批准。本文其余内容保留调研时的分析与行号，不作为现状描述。
- 目标：按职责拆分、冻结协议行为、将缺陷修复与等价重构分开。
- 原则：Pythonic 的收益是状态清楚、函数可测、依赖单向，不是推导式更多；不做全仓格式化式大拆迁。
- 调研期间未编辑代码、未创建提交；调研结束时 `jj status` 确认工作区为空。
- 本文行号依据调研时的版本；实施前重新读取相关代码与调用方，不按过期行号直接修改。

### 现状对照（复核记录）

- 复核依据：阶段 4 实施后重新读取 `api/`、`chaoxing_app/` 与调用方，并在仓库外运行离线探针（不联网）；离线回归基线为 `uv run --python 3.13 python -m unittest discover -s tests -t .`。
- `api/answer.py` 已删除并拆为 `api/answer/` 包：查询管道 `core.py`、缓存 `cache.py`、回退 `fallback.py`、注册表 `registry.py`、各 provider `providers/`。本文其余部分凡引用 `api/answer.py` 的行号都已失效，仅作调研时记录保留。
- 复核发现阶段 4 拆包本身引入了一处回归：`api/answer/core.py` 丢了 `sub` 与 `CacheDAO` 两个导入，题库启用时 `query`/`query_all` 首行即抛 `NameError`。已在 change `qvpsutuu` 修复并补回归，见下方「拆包回归」。
- 第四节五个缺陷在复核时仍然存在，当前位置与实测证据如下：
  - Session 反复重建：`api/base.py:46-49` 的单例 `__new__` 与 `api/base.py:51-60` 每次调用都重建 Session 的 `__init__`；`get_session()`（`:67-69`）经 `cls()` 触发构造。
  - 单题查询丢答案：`api/answer/core.py:104-119`，缓存未命中分支把 `self._query()` 的结果赋给 `answer`（`:105`）后未返回，最终落到 `:119` 的 `return None`；批量路径 `query_all`（`:121-179`）正常。同一名字 `cache_dao` 只在 `:99` 的缓存分支绑定，反馈分支 `:112` 使用的是未绑定的局部名（探针实测抛 `UnboundLocalError`）。
  - 缓存跨实例竞争：`api/answer/cache.py:24`，每个 `CacheDAO` 实例各自持有 `RLock`。**已动态复现**：两个实例并发各写 200 条，期望 400 条、实际落盘 6 条、丢 394 条；Windows 上还会出现 `os.replace` 报 `WinError 5 拒绝访问` 与 `_read_cache` 报 `Permission denied`（一个线程持有目标文件时另一线程的原子替换失败）。
  - 测验状态跨任务共享：`api/base.py:292` 构造时归零、`:1083` 判定、`:1180` 自增；`chaoxing_app/cli.py:115` 在整个运行中只创建一个 `Chaoxing` 实例并复用给所有任务。
  - 直播失败未向外传播：`chaoxing_app/jobs.py:77` 丢弃 `run_live()` 的返回值，随后直接返回 `StudyResult.SUCCESS`。
- 「共享题库反馈污染」仍属未复现的推断；「缓存跨实例丢更新」已由探针复现，不再是推断。
- 阶段 1 要求的脱敏 HTML/JSON、缓存与请求样本没有独立留档；阶段 5-6 实施前需按当前路径重新采集。
- 本文状态段的授权范围未变化：只授权等价重构；第四节缺陷修复需单独批准，其中「补回拆包丢失的导入」属于恢复拆包前的等价行为，已作为独立 fix 处理。

### 拆包回归（阶段 4 引入，已修复）

- 现象：`api/answer/core.py` 使用 `sub(...)`（`query` 内 `:92`/`:93`，`query_all` 内同名处理）与 `CacheDAO()`（`:99`/`:128`），但拆包提交 `ae64220` 生成的模块导入区没有这两个名字；拆包前的 `api/answer.py` 同时有 `from re import sub` 与 `class CacheDAO`。运行时 `hasattr(api.answer.core, 'sub')` 与 `hasattr(api.answer.core, 'CacheDAO')` 都是 `False`。
- 影响：题库启用（`DISABLE=False`）时 `query`/`query_all` 第一步就抛 `NameError`。`api/base.py:997` 的调用不在该处 `try` 内，异常经 `chaoxing_app/jobs.py` 的线程包装存入 `_error`，`run()` 随即以 `shutdown(immediate=True)` 收尾并重抛，整个学习流程中断；无题库配置时走 `DummyTiku` 提前返回，所以默认配置下不易察觉。
- 修复：change `qvpsutuu` 补回 `from re import sub` 与 `from api.answer.cache import CacheDAO`，并新增 `tests/test_answer_query.py` 覆盖查询管道（导入完整性、批量查询写缓存、缓存命中跳过 provider、题号归一化复用缓存键、停用短路）。
- 测试盲区：此前的 103 项回归只覆盖注册表顺序、实例默认值与日志缓冲，从未调用 `query`/`query_all`；「`api/answer/` 各类的 AST 与迁移前完全相同」的比对也不覆盖模块级导入。后续阶段应按调用路径补测试，而不是只比对类体。
- 两条仍待授权的查询缺陷（单题丢答案、反馈分支未绑定 `cache_dao`）在这份新测试里以 `expectedFailure` 标记，修复后必须移除标记。

## 一、优先施工点

| 现状与证据 | 施工方向 |
| --- | --- |
| `api/base.py` 集中会话、登录、课程、视频、测验、签到等；调研时视频流程从 `:660` 开始，测验流程从 `:994` 开始（复核时 `study_video` 在 `:758`、`study_work` 在 `:898`，全文 1528 行） | 保留 `Chaoxing` 业务入口，拆出会话、视频、测验实现 |
| `api/answer.py`（拆分前路径，已拆为 `api/answer/`）混合缓存、查询管道、回退链、各题库和手动交互 | 按查询核心、缓存、回退、provider 拆包，复用现有 registry |
| `api/decode.py:38-47,124-143` 重复查询 DOM；`:247-249` 原地修改任务卡片 | 缓存局部节点、明确输入输出契约；是否取消原地修改单独判定 |
| `api/answer.py:162-184`、`:142-146`（拆分前路径）多组 property 只转发字段；可变运行状态用大写类属性表达 | 无校验属性改普通实例属性；配置常量与运行状态分开 |
| `api/logger.py:16-20` 从 `sys.modules` 找手动锁，视频也直接依赖 `TikuManual` | 抽出唯一、轻量的终端交互状态，消除题库与日志的反向耦合 |
| `api/cookies.py:15-18`、`api/cipher.py:38-45` 循环拼接字符串或 bytes；异常类重复实现父类构造 | 使用 `join`、bytes 聚合、标准库类型与简洁异常定义，保持格式不变 |

题库已有 `PROVIDER_REGISTRY`、`TikuFallback`；通知已有工厂。不再造第二套工厂、通用重试框架或万能 HTTP 基类。

## 二、目标结构与接口迁移

建议先做到以下粒度，不给每个请求造一个类：

```text
api/
├── client.py             # Chaoxing：业务入口与短流程
├── models.py             # Account、StudyResult、少量共享结构类型
├── session.py            # 会话生命周期、Cookie 同步、登录协调、限流
├── video.py              # 参数/签名、上报、验证码恢复、播放循环
├── work.py               # 测验获取、组表、提交、判分、重做
├── decode.py             # HTML/JSON → 结构化数据
├── answer_check.py       # 纯答案规则
├── answer/
│   ├── core.py           # 查询管道与实例状态
│   ├── cache.py          # 现有 JSON 缓存
│   ├── fallback.py       # 按配置顺序回退
│   ├── registry.py       # 现有注册表与构造入口
│   └── providers/
│       ├── traditional.py
│       ├── ai.py
│       ├── siliconflow.py
│       └── manual.py
├── interaction.py        # 手动输入锁及交互状态
├── live.py               # 直播请求与执行流程
├── notification.py       # 暂留单文件
├── cookies.py
├── cipher.py
├── config.py
├── exceptions.py
├── font_decoder.py
└── cxsecret_font.py
```

### 迁移契约

- 迁移全部仓库内调用方，删除旧 `base.py`、`answer.py` 路径及无用别名，不留兼容壳。
- `Chaoxing.study_*` 的业务入口和返回语义先保留。
- 依赖方向为 `client → session/video/work`、`live → session`、`session → cookies/config`。
- `video/work` 使用传入的明确依赖与共享类型，不反向运行时导入 `client`。
- `models.py` 只容纳真正跨模块共享的类型，不为了目录对称建立对象体系。
- `live_process.py` 的单静态方法可迁为 `live.py` 顶层流程，迁移调用方后删除旧文件；返回值传播属于另一个缺陷修复项。
- 将 `process.py` 中进度展示与学习次数编排的职责分别审查；不为了文件数量对称额外拆类。
- 变更导出符号前重新查引用；语言服务可用时使用语言服务重命名或引用查询。

### 类型策略

- 远端字典使用 `TypedDict`、`Literal` 描述，不强行把整份 JSON 转成对象。
- `Account`、内部判分结果等固定结构使用 `dataclass`。
- 配置改具名字段，但保留现有字段名、默认值和转换规则。
- 不把所有 `None`、异常、状态码统一成一种“标准结果”，它们现在含义不同。

## 三、施工顺序与验收

| 阶段 | 工作内容 | 验收条件 |
| --- | --- | --- |
| 1. 固定行为边界 | 准备脱敏 HTML/JSON、缓存及请求样本，明确哪些行为必须保留 | 覆盖解析结果、表单内容、provider 顺序和任务状态；不把已知 bug 固化成永久测试 |
| 2. 纯函数与小模块 | 整理 Cookie 编解码、答案规则、加密聚合、类型和无用代码 | Cookie 含 `=` 的值不变；固定输入加密字节一致；答案分隔符优先级不变 |
| 3. 数据解析 | 减少重复 DOM 查询，抽出作答记录解析与判分纯函数 | 未开放、已完成、缺字段、直播识别、字体题目、`parse_ok` 等边界一致 |
| 4. 题库拆包 | 搬缓存、核心、回退、providers；统一公共查询步骤的表达 | 缓存命中、批量索引、逐题回退、校验豁免、反馈跳缓存规则不变 |
| 5. 会话与交互解耦 | 分离 Session 管理、手动锁、日志和进度展示 | 会话策略有明确契约；手动输入时无日志穿插；线程及资源可回收 |
| 6. 测验与视频拆分 | 先抽请求和表单构造，再抽流程；合并直播的单静态方法包装 | 请求参数、签名、保存/提交、重做次数及返回值一致；执行离线流程 smoke |

### 提交与执行纪律

- 每阶段一个或数个单一职责的 Jujutsu change，同步测试、调用方与 `docs/`，不攒成一次超大提交。
- 提交信息采用中文、gitmoji、约定式提交；等价重构与行为修复分别提交。
- 原地输入修改、默认值、异常吞吐、生命周期、重试顺序都属于需要显式审查的契约，不能因“更简洁”悄悄改变。
- 每个非平凡阶段运行相关回归和实际 smoke；测试通过不等于线上协议通过。
- 只读探针与临时样本放仓库外；真实 Cookie、账号、token、API key 不纳入 change。

## 四、需要单独处理的缺陷

这些不属于“写法更 Pythonic”，应独立批准与 `fix` 提交，不在等价搬迁中偷偷修正。阶段 4 拆包自己引入的回归（缺失导入）见上面「拆包回归」，已作为独立 fix 修复。

| 问题 | 证据及处理建议 |
| --- | --- |
| Session 反复重建 | 调研位置 `api/base.py:42-65`，复核位置 `:46-60`；离线探针确认两次获取不是同一 Session，新增 header 丢失。修复前明确并发策略，不能简单加初始化标志就宣称线程安全 |
| 单题查询丢答案 | 调研位置 `api/answer.py:243-264`，拆包后 `api/answer/core.py:104-119`；探针得到单题 `None`、批量 `['B']`。反馈分支还引用未绑定的 `cache_dao`（复核为 `core.py:112`，探针实测 `UnboundLocalError`）。单独修查询管道 |
| 缓存跨实例竞争 | 调研位置 `api/answer.py:37-39,132-137`，拆包后 `api/answer/cache.py:24`：每个 DAO 独立锁。**已复现**：两实例并发各写 200 条，落盘 6 条、丢 394 条，并伴随 `WinError 5`/`Permission denied`。原子替换能防文件损坏，但不能保证不丢更新；修法需先定一致性契约 |
| 测验状态跨任务共享 | 调研位置 `api/base.py:388,1179,1276`，复核位置 `api/base.py:292,1083,1180` 的 `rollback_times`；`chaoxing_app/cli.py:115` 单实例跨任务复用。反馈也写入共享题库。缩小为每测验状态会改变提交行为，需要独立处理 |
| 直播失败未向外传播 | `chaoxing_app/jobs.py:77` 忽略 `run_live()` 返回值。改为失败会触发章节重试，不应夹在文件合并里 |

### 修复契约（实施前定案）

授权范围已由用户扩展为"修复本节全部缺陷"；仍保持等价重构与行为修复分开提交，每项一个独立 `fix` change。下列行为差异在动代码前记录：

1. 题库查询管道（`api/answer/core.py`）
   - 契约：`query()` 与 `query_all()` 对同一输入必须给出相同答案；缓存未命中时把 provider 结果经 `check_answer` 校验后返回并回写缓存；存在 `work_feedback` 时按既有规则跳过缓存读取、成功后仍回写。
   - 行为差异：修复前 `query()` 缓存未命中即返回 `None`（答案被丢弃），反馈分支还会因 `cache_dao` 未绑定抛 `UnboundLocalError`；修复后与批量路径一致。缓存命中、反馈跳缓存、手动校验豁免与既有日志文案不变。
   - 验证：`tests/test_answer_query.py` 移除两处 `expectedFailure`，并新增反馈模式跳缓存用例。
2. 缓存并发一致性（`api/answer/cache.py`）
   - 契约：指向同一缓存文件的 `CacheDAO` 实例共享一把 `threading.RLock`（按解析后的文件路径登记），`get_cache`/`add_cache` 的读-改-写在锁内完成；跨进程并发不在本轮范围，不引入跨进程锁。
   - 读取失败差异：文件不存在或 JSON/编码损坏仍返回 `{}` 并保留备份与原子替换；其他 `OSError`（如 Windows 共享冲突）按 `READ_RETRY_TIMES` 有限重试，仍失败则按"缓存不可用"处理——读取视为未命中（`get_cache` 返回 `None`，交给题库继续查询），写入跳过并记日志，绝不把整表覆盖成只剩新键。
   - 行为差异：并发写同一文件由"整表被清空重写"变为"写入全部保留"；单线程行为不变。
   - 验证：新增并发回归（两实例并发写入后断言键数完整）。
3. Session 生命周期（`api/base.py`）
   - 契约：进程内只构造一次 `requests` Session，构造过程加锁；cookie 变更通过 `update_cookies()` 显式同步到既有会话；`get_session()` 始终返回同一对象。
   - 行为差异：修复前每次获取都新建 Session（顺带重读 cookies 文件、重设 header）；修复后对象稳定、内存态不再丢失，但中途手工修改 cookies 文件需显式调用 `update_cookies()` 才会生效。
   - 验证：新增回归断言对象同一且运行时 header 保留。
4. 测验重做计数（`api/base.py`）
   - 契约：重做计数是每次 `study_work` 调用的局部状态，不再挂进程级 `Chaoxing` 实例。
   - 行为差异：修复前任一任务重做后，后续测验第一轮即满足 `rollback_times >= 1` 而直接提交（绕过"覆盖率不足则只保存"的门槛）；修复后每个测验独立判定。`StudyResult` 语义不变。
   - 验证：提交策略无法离线验证，记录为未覆盖项，由"状态不跨调用"的代码约束与本文保证。
5. 直播失败传播（`chaoxing_app/jobs.py`、`api/live_process.py`）
   - 契约：`run_live()` 返回 `False` 时该任务点返回 `StudyResult.ERROR`，交给既有章节重试；每分钟提交失败后的一次重试结果记入日志，但不改变控制流（避免重复上报已计入的时长）。
   - 行为差异：修复前失败也返回 SUCCESS 并视为完成；修复后失败会触发章节重试，可能重复上报直播时长，需在可控测试课程下验收。
   - 验证：新增回归（`run_live` 返回 `False` 时 `process_job` 返回 ERROR）；真实重投列入线上验收清单。
6. 无题库实例的判定顺序（`api/base.py:899`）
   - 契约：`tiku` 为 `None` 或已停用都跳过该任务点并返回 SUCCESS，与既有 `DISABLE` 分支一致。
   - 行为差异：修复前 `tiku=None` 先访问 `.DISABLE` 抛 `AttributeError`（经线程包装会中断流程）；修复后按原注释意图跳过。CLI 路径始终传入实例，行为不变。

### 实际调研输出

仓库外临时目录中的离线探针，没有发送网络请求，观察到：

```text
session identity preserved: False
session header preserved: None
single query result: None
batch query result: ['B']
```

第二次探针（补上缺失导入后隔离其余缺陷，另含并发缓存场景）观察到：

```text
single query result: None
batch query result: ['B']
feedback-mode single query raised: UnboundLocalError cannot access local variable 'cache_dao' where it is not associated with a value
session identity preserved: False
session header preserved: None
cache keys expected: 400 stored: 6 lost: 394
```

第一次探针在缺失导入未被发现时运行，第二次补上导入以隔离其余缺陷；两次都只读、未联网。

缓存丢更新已由第二次探针复现（见上）；共享反馈污染仍未动态复现，不得将推断写成已证实故障。

### 推荐处理顺序

查询缺陷先修；会话与跨任务状态先明确契约，再修，再拆流程。不把已知有问题的实现搬到漂亮的新目录里就算完工。

会话策略、反馈作用域、缓存并发保证的具体实现尚未定案；实施时先用现有调用与复现证据选择保守方案。不得未经批准引入跨进程缓存锁、线程本地 Session 或新的共享状态机制。

## 五、必须保留的行为边界

### 题库与答案

- 保留 provider 配置名称、配置顺序及重复项；未知 provider 目前导致整链禁用，不改成静默跳过。
- 回退只处理仍未命中的题目，保持原始索引映射，不能因批量长度异常而错配答案。
- 保留手动模式与回退包装器的校验豁免；手动输入自身的校验与自动题库规则不能机械合并。
- `cut` 按固定分隔符顺序取首个可切分结果，不能直接替换为同时匹配全部分隔符的正则。
- 缓存以清洗后的 title 为 key；保留损坏恢复、备份、临时文件及原子替换机制。
- 反馈模式当前跳过缓存读取，但成功答案仍可回写；修复反馈链感知问题与增加 provider 反馈能力分开处理。
- 配置可能已由 CLI 转换出数值，不能统一假定为 `dict[str, str]`。

### 平台协议与任务结果

- 保留视频首次与后续上报参数差异、签名盐、单位换算、rt 探测顺序及 Video → Audio 兜底。
- 保留测验保存时不提交随机答案、覆盖率判定、重做开关、次数和判分优先级。
- 保留 `StudyResult` 对外语义：保存成功、成绩未知、部分无法可靠判分的情况目前也可能返回 SUCCESS；不能直接解释成服务端确认任务完成。
- 传输重试、题页重试、成绩记录轮询、验证码恢复、业务重做和章节重试是不同层，不统一套一层 retry。
- 通知 provider 的 JSON、query params、form data 格式及错误处理差异不变。
- Cookie 持久化暂不新增 domain/path 等字段，不改变现有 name/value 文本协议。
- 手动交互期间日志缓冲、解锁后的输出时机和进度展示协同保持一致；日志初始化改为显式生命周期属于另一个行为变化。

## 六、明确不做

- 不迁移 `asyncio`，不统一换成 `httpx`。
- 不更换加密库、签名算法、请求参数或表单字段。
- 不统一扩大重试，尤其不自动重试有副作用的提交请求。
- 不改变随机答案、相似度阈值、覆盖率、保存/提交和重做策略。
- 不擅自把 `StudyResult.SUCCESS` 改成“服务端已确认完成”。
- 不顺手改缓存 key、持久化格式、TLS 或缺依赖降级策略。
- 不顺手增加新 provider 能力、遥测、校验框架或通用 HTTP 抽象。

## 七、推荐起步与验证限制

最有收益的第一批：纯规则与解析整理 → 单题查询修复 → 题库拆包。

视频和测验是高风险区，放在契约与验证手段齐备后施工。线上验收先跑只读登录和课程查询；会提交或上报进度的场景需要可控测试课程，不能拿真实作业试刀。

既有 35 项回归已在前次 CLI 重构中通过；阶段 2-4 完成后离线回归为 103 项通过，但仍不足以证明本方案实施后的 API 行为。调研期间没有运行完整测试、线上账号、题库、直播或提交操作；线上路径与打包（PyInstaller/Windows、Docker）在复核时同样未运行，后续必须按实际改动重新验证。
