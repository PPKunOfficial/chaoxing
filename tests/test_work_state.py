# -*- coding: utf-8 -*-
"""测验重做计数的状态归属回归。

契约见 `.agents/api重构施工方案.md` 第四节「修复契约」：重做计数是每次
`study_work` 调用的局部状态。以前它挂在共享的 `Chaoxing` 实例上，一次运行
里任一任务重做后，后续测验第一轮就会满足 `rollback_times >= 1`，从而绕过
"覆盖率不足则只保存不提交"的门槛。

提交策略本身需要真实课程与网络才能端到端验证，这里只锁定状态归属，防止
共享状态被重新引入。
"""
import inspect
import unittest

from api.answer.registry import DummyTiku
from api.base import Chaoxing


class WorkRetryStateTest(unittest.TestCase):
    def test_client_carries_no_work_retry_state(self):
        chaoxing = Chaoxing(account=None, tiku=DummyTiku())
        self.assertFalse(hasattr(chaoxing, "rollback_times"))

    def test_client_source_does_not_reference_shared_retry_counter(self):
        self.assertNotIn("self.rollback_times", inspect.getsource(Chaoxing))


if __name__ == "__main__":
    unittest.main()
