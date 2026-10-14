# -*- coding: utf-8 -*-
"""章节检测判分回归测试: 作答记录解析、parse_ok 标记、答案归一化与逐题判分."""
import unittest

from api.answer_check import grade_work_detail, normalize_answer_text
from api.decode import parse_work_record_detail


class NormalizeAnswerTextTest(unittest.TestCase):
    def test_judgement_variants(self):
        """对/错 与 true/false 两套表述应归一到同一值."""
        self.assertEqual(normalize_answer_text('true'), normalize_answer_text('对'))
        self.assertEqual(normalize_answer_text('false'), normalize_answer_text('错误'))
        self.assertNotEqual(normalize_answer_text('true'), normalize_answer_text('false'))

    def test_judge_letter_aliases(self):
        """单字母别名 T/F/1/0/Y/N/X 应与 true/false 归一一致(不被字母数字短路)."""
        self.assertEqual(normalize_answer_text('T'), 'TRUE')
        self.assertEqual(normalize_answer_text('F'), 'FALSE')
        self.assertEqual(normalize_answer_text('1'), 'TRUE')
        self.assertEqual(normalize_answer_text('0'), 'FALSE')
        self.assertEqual(normalize_answer_text('Y'), 'TRUE')
        self.assertEqual(normalize_answer_text('N'), 'FALSE')
        self.assertEqual(normalize_answer_text('X'), 'FALSE')

    def test_letter_answer_kept(self):
        """纯字母答案不能被前缀剥离破坏."""
        self.assertEqual(normalize_answer_text('B'), 'B')
        self.assertEqual(normalize_answer_text('a'), 'A')
        self.assertEqual(normalize_answer_text('10'), '10')

    def test_letter_prefix_stripped(self):
        """'B.按ESC键' 与 '按ESC键' 应视为同一答案."""
        self.assertEqual(normalize_answer_text('B. 按 ESC 键'), normalize_answer_text('按ESC键'))

    def test_same_format_multi_choice(self):
        """同格式的多选答案归一后必然相等(跨格式差异由分数兜底, 见方案 F2 局限)."""
        self.assertEqual(normalize_answer_text('A,B,C'), normalize_answer_text('ABC'))

    def test_empty_and_none(self):
        self.assertEqual(normalize_answer_text(None), '')
        self.assertEqual(normalize_answer_text(''), '')


def _detail_html(answer_block):
    return (
        '<div class="TiMu singleQuesId" data="100">'
        '<div class="Zy_TItle"><div>题干</div></div>'
        + answer_block +
        '</div>'
    )


class ParseWorkRecordDetailTest(unittest.TestCase):
    def test_exact_structure(self):
        """原有精确结构必须继续命中(向后兼容)."""
        html = _detail_html(
            '<span>我的答案：</span><div class="fl answerCon"> B </div>'
            '<span>正确答案：</span><div class="fl answerCon"> B </div>')
        qs = parse_work_record_detail(html)
        self.assertEqual(len(qs), 1)
        self.assertTrue(qs[0]['parse_ok'])
        self.assertEqual(qs[0]['my_answer'], 'B')

    def test_extra_class_variant(self):
        """answerCon 带额外 class 的页面变体应命中宽松模式."""
        html = _detail_html(
            '<span>我的答案：</span><div class="fl answerCon colorDeep">A</div>'
            '<span>正确答案：</span><div class="fl answerCon colorGreen">B</div>')
        qs = parse_work_record_detail(html)
        self.assertTrue(qs[0]['parse_ok'])
        self.assertEqual(qs[0]['my_answer'], 'A')
        self.assertEqual(qs[0]['correct_answer'], 'B')

    def test_span_variant(self):
        """答案写在 span 而非 div 的页面变体应命中."""
        html = _detail_html(
            '<span>我的答案：</span><span class="colorRed">true</span>'
            '<span>正确答案：</span><span class="colorGreen">对</span>')
        qs = parse_work_record_detail(html)
        self.assertTrue(qs[0]['parse_ok'])
        self.assertEqual(qs[0]['my_answer'], 'true')

    def test_missing_answer_marks_unknown(self):
        """任一侧未命中 → parse_ok=False, 避免空串比较误判全错."""
        html = _detail_html('<span>我的答案：</span><div class="fl answerCon">A</div>')
        qs = parse_work_record_detail(html)
        self.assertFalse(qs[0]['parse_ok'])
        self.assertEqual(qs[0]['my_answer'], 'A')
        self.assertEqual(qs[0]['correct_answer'], '')


class GradeWorkDetailTest(unittest.TestCase):
    def test_all_correct_passes(self):
        detail = [{"parse_ok": True, "my_answer": "B", "correct_answer": "B",
                   "title": "题", "type_label": "单选题"}]
        all_correct, feedback, unknown = grade_work_detail(detail)
        self.assertTrue(all_correct)
        self.assertEqual(feedback, [])
        self.assertEqual(unknown, 0)

    def test_wrong_answer_produces_feedback(self):
        detail = [{"parse_ok": True, "my_answer": "A", "correct_answer": "B",
                   "title": "题", "type_label": "单选题"}]
        all_correct, feedback, unknown = grade_work_detail(detail)
        self.assertFalse(all_correct)
        self.assertEqual(unknown, 0)
        self.assertEqual(len(feedback), 1)
        self.assertIn("题目：题", feedback[0])
        self.assertIn("正确答案：B", feedback[0])

    def test_judgement_variants_are_equal(self):
        detail = [{"parse_ok": True, "my_answer": "true", "correct_answer": "对",
                   "title": "", "type_label": ""}]
        all_correct, _, _ = grade_work_detail(detail)
        self.assertTrue(all_correct)

    def test_unparsed_answer_counts_as_unknown(self):
        detail = [{"parse_ok": False, "my_answer": "A", "correct_answer": ""}]
        all_correct, feedback, unknown = grade_work_detail(detail)
        self.assertFalse(all_correct)
        self.assertEqual(feedback, [])
        self.assertEqual(unknown, 1)

    def test_empty_detail(self):
        self.assertEqual(grade_work_detail([]), (True, [], 0))


if __name__ == '__main__':
    unittest.main()
