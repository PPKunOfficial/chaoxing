# -*- coding: utf-8 -*-
"""答案校验与切分规则的边界回归。

`cut` 的分隔符优先级和手动/回退题库的校验豁免属于行为契约，见
`.agents/api重构施工方案.md` 第五节。
"""
import unittest

from api.answer_check import (
    CUT_CHARACTERS,
    check_answer,
    check_completion,
    check_judgement,
    check_multiple,
    check_single,
    cut,
)


class CutTest(unittest.TestCase):
    def test_separators_are_tried_in_fixed_order(self):
        """先出现的分隔符先切分：逗号优先于空格，空格优先于顿号。"""
        self.assertEqual(cut("A,B C"), ["A", "B C"])
        self.assertEqual(cut("A B"), ["A", "B"])
        self.assertEqual(cut("A B、C"), ["A", "B、C"])
        self.assertEqual(cut("A\nB,C"), ["A", "B,C"])
        self.assertEqual(CUT_CHARACTERS[0], "\n")

    def test_multiple_separators_collapse_to_first_hit(self):
        self.assertEqual(cut("A||B"), ["A", "B"])
        self.assertEqual(cut("|A|B|"), ["A", "B"])
    def test_unsplittable_answer_is_returned_whole(self):
        self.assertEqual(cut("AB"), ["AB"])
        self.assertEqual(cut("B"), ["B"])
        # 仅由分隔符组成时切不出内容, 按契约继续尝试后续分隔符, 最终原样返回
        self.assertEqual(cut("|||"), ["|||"])

    def test_empty_inputs_return_none(self):
        self.assertIsNone(cut(None))
        self.assertIsNone(cut(""))
        self.assertIsNone(cut("   "))

    def test_non_string_input_is_stringified(self):
        self.assertEqual(cut(12), ["12"])


class CheckSingleTest(unittest.TestCase):
    def test_comma_is_not_a_multiple_answer_marker(self):
        self.assertTrue(check_single("A,B"))
        self.assertTrue(check_single("答案，说明"))

    def test_strong_delimiters_mark_multiple_answers(self):
        for answer in ["A\nB", "A|B", "A#B", "A\tB", "A\rB", "A、B"]:
            with self.subTest(answer=answer):
                self.assertFalse(check_single(answer))

    def test_none_and_blank(self):
        self.assertFalse(check_single(None))
        self.assertFalse(check_single("   "))


class CheckMultipleAndCompletionTest(unittest.TestCase):
    def test_multiple_accepts_any_non_empty_answer(self):
        self.assertTrue(check_multiple("AB"))
        self.assertTrue(check_multiple("A,B"))
        self.assertFalse(check_multiple(""))
        self.assertFalse(check_multiple(None))

    def test_completion_only_checks_length(self):
        self.assertTrue(check_completion(["a"]))
        self.assertFalse(check_completion(""))


class CheckJudgementTest(unittest.TestCase):
    TRUE_LIST = ["对", "正确"]
    FALSE_LIST = ["错", "错误"]

    def test_builtin_keywords(self):
        for answer in ["true", "T", "1", "对", "正确", "√", "是", "yes", "y"]:
            with self.subTest(answer=answer):
                self.assertEqual(check_judgement(answer, self.TRUE_LIST, self.FALSE_LIST), 1)
        for answer in ["false", "F", "0", "错", "错误", "×", "否", "no", "n", "不对", "不正确"]:
            with self.subTest(answer=answer):
                self.assertEqual(check_judgement(answer, self.TRUE_LIST, self.FALSE_LIST), 0)

    def test_configured_lists_are_case_insensitive(self):
        self.assertEqual(check_judgement("RIGHT", ["Right"], ["Wrong"]), 1)
        self.assertEqual(check_judgement("wrong", ["Right"], ["Wrong"]), 0)

    def test_unknown_value_returns_minus_one(self):
        self.assertEqual(check_judgement("maybe", self.TRUE_LIST, self.FALSE_LIST), -1)


class _StubTiku:
    is_manual = False
    skip_answer_validation = False
    true_list = ["对"]
    false_list = ["错"]


class CheckAnswerTest(unittest.TestCase):
    def test_manual_and_fallback_wrappers_are_exempt(self):
        manual = _StubTiku()
        manual.is_manual = True
        self.assertTrue(check_answer("任意内容", "single", manual))

        fallback = _StubTiku()
        fallback.skip_answer_validation = True
        self.assertTrue(check_answer("任意内容", "single", fallback))

    def test_unknown_type_is_accepted(self):
        self.assertTrue(check_answer("任意内容", "shortanswer", _StubTiku()))

    def test_type_mismatch_is_rejected(self):
        stub = _StubTiku()
        self.assertFalse(check_answer("A\nB", "single", stub))
        self.assertFalse(check_answer("对", "multiple", stub))

    def test_matching_type_is_accepted(self):
        self.assertTrue(check_answer("对", "judgement", _StubTiku()))
        self.assertTrue(check_answer("填空内容", "completion", _StubTiku()))
        self.assertTrue(check_answer("A", "single", _StubTiku()))


if __name__ == "__main__":
    unittest.main()
