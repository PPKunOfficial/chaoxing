# API 离线行为对照

这些是人工构造的合成输入及 `56484f37` 当前实现的请求预期，**不是线上响应采集**。所有 ID 和令牌占位符均为虚构；不含账号、Cookie 或服务 key。

- `video.json`：固定时间、课程/任务/视频元数据、签名向量及首次/后续/完成上报预期。首次上报 `isdrag=4`、`playingTime=duration`；后续 `isdrag=3`。预期摘要独立按施工方案签名格式计算，测试不得由被测方法生成预期。
- `work.html`、`work.json`：五种题型的合成页面、固定题库答案、取题参数、提交头及各分支表单预期。覆盖显式保存、覆盖率不足保存（随机答案留空）、门槛提交、手动模式豁免、重做上限与单次调用的重做状态。
- `tests/test_api_contracts.py`：真实解析/组表/视频流程与替身 Session；每次请求立即深拷贝，阻止可变字典复用掩盖历史差异。测试禁止实际 HTTP 发送，不初始化 OCR 或真实题库。

复跑：`.venv/bin/python -m unittest tests.test_api_contracts -v`。

解析边界继续由 `test_decode.py` 覆盖；缓存格式/竞争、provider 顺序/回退、任务状态分别复用 `test_answer_cache.py`、`test_answer_query.py`、`test_answer_package.py`、`test_work_state.py`、`test_job_processor.py`，不复制样本或测试。既有缺陷（直播最终判定、反馈链感知等）不是本目录冻结的永久要求。

限制：离线替身无法证明服务器接受这些请求，也不覆盖真实响应、验证码/登录恢复、直播或有副作用的线上端到端验收。
