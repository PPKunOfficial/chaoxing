# 踩坑

## 检查误用系统 Python

前次检查使用未安装项目依赖的系统 Python，出现 `tqdm`、`loguru` 导入失败；项目虚拟环境的回归通过。使用 `uv run --python 3.13` 或已安装项目依赖的解释器，不把环境缺依赖误判为代码回归。

## 任务列表计数时机

调度重构时在构造器缓存任务数量，随后 `run()` 前清空或扩展列表，曾导致空任务等待无法退出。已将计数放到 `run()` 入队前，并覆盖空任务与异常退出。修改线程生命周期时同时检查逻辑任务数、两队列计数和线程回收。

## API 会话与单题查询缺陷

仓库外离线探针观察到连续 `SessionManager.get_session()` 返回不同对象，上一份 header 丢失；题库缓存未命中时单题查询返回 `None`，同输入批量查询返回答案。尚未修复，施工方案记录了单独修复边界。缓存跨实例丢更新和反馈跨任务污染只是待验证风险，不宣称已复现。

## 字体映射不是一一对应

字体映射 smoke 曾错误假定任意正向键经反向查询必然返回同名键；多个字形名可对应相同哈希。使用已知键的哈希值与反向结果的哈希一致性验证，不测试并不存在的一一映射不变量。

## Markdown 链接校验误识别命令

README 的示例命令包含 `[retry|ask|continue](可选)`，简单链接正则曾将其识别为文件链接。检查链接前排除 fenced code 和 inline code，不能把命令参数当作本地路径。

## jj 元数据不随 clone 复制

重新 `git clone` 得到的目录只有 `.git/`，即使 `.gitignore` 里保留了 `.jj/` 规则也不会带来 jj 元数据，此时 `jj` 报 `There is no jj repo in "."`。用 `jj git init --colocate` 重建并 `jj bookmark track main@origin`，再用 `jj log` 核对 jj 推出的 change ID 是否与旧记录一致（一致即说明是同一仓库历史，没有重建历史）。

## core.autocrlf 让 jj 全树报脏

全局 `core.autocrlf=true` 时，clone 出的工作树是 CRLF、仓库内容按 LF 存储；git 因归一化判定干净，jj 按字节比对会把全部文件报成已修改。修复：`git config core.autocrlf false`，再 `git rm --cached -r .` + `git reset --hard` 让工作树按 LF 落盘。该操作会覆盖未提交改动，先确认 `git status` 为空；忽略文件与未跟踪文件不受影响。不要把这个假改动当成真实修改提交。

## jj 模板参数被当作位置参数

jj 0.45.1 在本机执行 `jj log -T '...'` 或 `--template '...'` 时会被解析成 fileset，报 `Failed to parse fileset: Syntax error`。改用默认 `jj log` 输出即可，不据此判断仓库状态损坏。

## 拆包时丢掉模块级导入

阶段 4 生成 `api/answer/core.py` 时漏掉了 `from re import sub` 与 `from api.answer.cache import CacheDAO`，而正文同时保留 `sub(...)`、`CacheDAO()`：题库启用时查询第一步就抛 `NameError`。旧回归只测注册表与实例状态，「各类 AST 与迁移前相同」的比对不覆盖模块级导入，所以两边都没拦住。用 `symtable` 走一遍即可发现函数内引用、模块里却没定义的全局名：

```python
import symtable
table = symtable.symtable(open(path, encoding="utf8").read(), path, "exec")
defined = set(table.get_identifiers())  # 再并入各函数内 global 赋值过的名字
```

搬迁模块后要补一条真正走调用路径的回归（如 `tests/test_answer_query.py`），只比对类体不够。

## 探针残留缓存让结论失真

`CacheDAO` 默认把 `cache.json` 写在当前工作目录；复跑离线探针时不换目录或清理，上一轮写入的答案会被命中，单题查询看起来「返回了答案」，会把真实缺陷掩盖掉。每次探针都换成干净目录，并确认没有 `cache.json` 残留。
