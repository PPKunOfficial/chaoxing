"""课程选择边界与进度格式生命周期回归。"""

import unittest
from unittest.mock import patch

from tqdm import tqdm

from chaoxing_app.cli import filter_courses, format_time, progress_time_format


class CourseSelectionTest(unittest.TestCase):
    def test_selection_deduplicates_class_not_course(self):
        first = {"courseId": "1", "clazzId": "a"}
        second = {"courseId": "1", "clazzId": "b"}
        other = {"courseId": "2", "clazzId": "c"}
        courses = [first, first.copy(), second, other]
        self.assertEqual(filter_courses(courses, [" 1 ", ""]), [first, second])

    def test_unmatched_selection_preserves_all_courses(self):
        courses = [{"courseId": "1", "clazzId": "a"}]
        self.assertEqual(filter_courses(courses, ["missing"]), courses)

    def test_interactive_selection_strips_spaces(self):
        courses = [
            {"courseId": "1", "clazzId": "a", "title": "一"},
            {"courseId": "2", "clazzId": "b", "title": "二"},
        ]
        with patch("builtins.input", return_value=" 2 , "), patch("builtins.print"):
            self.assertEqual(filter_courses(courses, None), [courses[1]])


class ProgressFormatTest(unittest.TestCase):
    def test_restores_formatter_after_failure(self):
        original = tqdm.format_sizeof
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with progress_time_format():
                self.assertEqual(tqdm.format_sizeof(3601), "01:00:01")
                raise RuntimeError("failure")
        self.assertIs(tqdm.format_sizeof, original)

    def test_duration_boundaries(self):
        for seconds, expected in [(59, "00:59"), (60, "01:00"), (3599, "59:59"), (3600, "01:00:00")]:
            with self.subTest(seconds=seconds):
                self.assertEqual(format_time(seconds), expected)
