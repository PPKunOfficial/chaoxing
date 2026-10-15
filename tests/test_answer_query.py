# -*- coding: utf-8 -*-
"""题库查询管道回归：导入完整性、缓存命中、标题归一化与停用短路。

阶段 4 拆包后 `api/answer/core.py` 丢了 `sub` 与 `CacheDAO` 两个导入，此前
只有注册表与实例状态的测试，从未调用 `query`/`query_all`，因此没有被发现。
本文件覆盖查询管道本身；`.agents/api重构施工方案.md` 第四节记录了两条仍待
单独授权的缺陷，用 `expectedFailure` 标记，修复后必须移除标记。
"""
import functools
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import api.answer.core as core
from api.answer.cache import CacheDAO
from api.answer.core import Tiku

CONFIG_PATH = "config_template.ini"


class ProbeTiku(Tiku):
    """记录收到的标题并返回固定答案的探针题库, 不发起任何网络请求。"""

    def __init__(self, answer="B", config_path=CONFIG_PATH):
        super().__init__(config_path)
        self.name = "probe"
        self.answer = answer
        self.seen_titles = []

    def _query(self, q_info):
        self.seen_titles.append(q_info["title"])
        return self.answer


def question(title, q_type="single"):
    return {"title": title, "type": q_type, "options": "A\nB\nC\nD"}


class QueryPipelineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_file = Path(self._tmp.name) / "cache.json"
        patcher = patch("api.answer.core.CacheDAO",
                        functools.partial(CacheDAO, file=str(self.cache_file)))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_core_module_exposes_regex_and_cache_helpers(self):
        """回归：拆包不得丢掉查询管道依赖的模块级名字。"""
        self.assertTrue(hasattr(core, "sub"))
        self.assertTrue(hasattr(core, "CacheDAO"))

    def test_batch_query_returns_provider_answers_and_writes_cache(self):
        tiku = ProbeTiku()
        tiku.DISABLE = False
        results = tiku.query_all([question("12. 题目标题（2.50分）")])

        self.assertEqual(results, ["B"])
        self.assertEqual(tiku.seen_titles, [". 题目标题"])
        with self.cache_file.open(encoding="utf8") as fp:
            self.assertEqual(json.load(fp), {". 题目标题": "B"})

    def test_cache_hit_skips_provider(self):
        tiku = ProbeTiku()
        tiku.DISABLE = False
        CacheDAO(str(self.cache_file)).add_cache(". 题目标题", "A")

        results = tiku.query_all([question("1. 题目标题")])

        self.assertEqual(results, ["A"])
        self.assertEqual(tiku.seen_titles, [])

    def test_numbered_variants_share_one_cache_key(self):
        """题号与分数被归一化掉, 同一题目不同编号复用同一缓存键。"""
        tiku = ProbeTiku()
        tiku.DISABLE = False

        first = tiku.query_all([question("1. 题目标题（2.00分）")])
        second = tiku.query_all([question("3. 题目标题（4.50分）")])

        self.assertEqual(first, ["B"])
        self.assertEqual(second, ["B"])
        self.assertEqual(tiku.seen_titles, [". 题目标题"])

    def test_disable_short_circuits_without_querying(self):
        tiku = ProbeTiku()
        tiku.DISABLE = True

        self.assertIsNone(tiku.query(question("1. 题目标题")))
        self.assertEqual(tiku.query_all([question("1. 题目标题"), question("2. 另一题")]), [None, None])
        self.assertEqual(tiku.seen_titles, [])

    def test_single_query_returns_provider_answer_on_cache_miss(self):
        """单题查询与批量查询必须同结果: 缓存未命中时返回 provider 答案并回写缓存。"""
        tiku = ProbeTiku()
        tiku.DISABLE = False

        self.assertEqual(tiku.query(question("1. 题目标题")), "B")
        self.assertEqual(tiku.seen_titles, [". 题目标题"])
        self.assertEqual(CacheDAO(str(self.cache_file)).get_cache(". 题目标题"), "B")

    def test_single_query_returns_cached_answer_without_provider(self):
        tiku = ProbeTiku()
        tiku.DISABLE = False
        CacheDAO(str(self.cache_file)).add_cache(". 题目标题", "C")

        self.assertEqual(tiku.query(question("1. 题目标题")), "C")
        self.assertEqual(tiku.seen_titles, [])

    def test_feedback_mode_single_query_skips_cache_and_still_writes(self):
        """重做模式跳过缓存读取, 但拿到答案后仍回写缓存。"""
        tiku = ProbeTiku()
        tiku.DISABLE = False
        tiku.work_feedback = "上一轮错误反馈"
        CacheDAO(str(self.cache_file)).add_cache(". 题目标题", "C")

        self.assertEqual(tiku.query(question("1. 题目标题")), "B")
        self.assertEqual(tiku.seen_titles, [". 题目标题"])
        self.assertEqual(CacheDAO(str(self.cache_file)).get_cache(". 题目标题"), "B")

    def test_single_query_discards_answer_of_wrong_type(self):
        """题型不符的答案被舍弃, 不写缓存。"""
        tiku = ProbeTiku()
        tiku.DISABLE = False
        tiku.answer = "对"

        self.assertIsNone(tiku.query(question("1. 题目标题", q_type="multiple")))
        self.assertIsNone(CacheDAO(str(self.cache_file)).get_cache(". 题目标题"))


if __name__ == "__main__":
    unittest.main()
