"""参数与配置解析的无网络边界测试。"""

import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

from chaoxing_app.config import (
    build_config_from_args,
    init_config,
    load_config_from_file,
    parse_args,
    str_to_bool,
)


class ConfigTestCase(unittest.TestCase):
    def load_ini(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.ini"
            path.write_text(content, encoding="utf8")
            return load_config_from_file(path)

    def test_ini_converts_only_expected_fields(self):
        common, tiku, notification = self.load_ini("""
[common]
username =  user
password =  secret
course_list =  a, , b,,
speed = 1.5
jobs = 2
retry_interval = 0
work_max_retries = 5
work_redo_enabled = YES
use_cookies = on
add_learning_count = false
target_count = 20
auto_sign = true
[tiku]
delay = 0.25
cover_rate = 0.8
submit = true
tokens = first,second
[notification]
provider = Telegram
tg_chat_id = 123
""")
        self.assertEqual(common, {
            "username": "user", "password": "secret", "course_list": ["a", "b"],
            "speed": 1.5, "jobs": 2, "retry_interval": 0.0,
            "work_max_retries": 5, "work_redo_enabled": True,
            "use_cookies": True, "add_learning_count": False,
            "target_count": 20, "auto_sign": "true", "notopen_action": "retry",
        })
        self.assertIsInstance(common["speed"], float)
        self.assertIsInstance(common["jobs"], int)
        self.assertIsInstance(common["retry_interval"], float)
        self.assertIsInstance(common["target_count"], int)
        self.assertEqual(tiku, {
            "delay": 0.25, "cover_rate": 0.8, "submit": "true",
            "tokens": "first,second",
        })
        self.assertEqual(notification, {"provider": "Telegram", "tg_chat_id": "123"})

    def test_ini_common_defaults_and_missing_sections(self):
        self.assertEqual(self.load_ini("[common]\n"), ({
            "notopen_action": "retry", "retry_interval": 1.0,
            "work_max_retries": 3,
        }, {}, {}))
        self.assertEqual(self.load_ini(""), ({}, {}, {}))

    def test_ini_invalid_work_max_retries_falls_back(self):
        for value in ("invalid", "", "1.5"):
            with self.subTest(value=value):
                common, _, _ = self.load_ini(f"[common]\nwork_max_retries={value}\n")
                self.assertEqual(common["work_max_retries"], 3)

    def test_ini_other_invalid_numbers_are_not_silently_replaced(self):
        for section, key in (
            ("common", "speed"), ("common", "jobs"),
            ("common", "retry_interval"), ("common", "target_count"),
            ("tiku", "delay"), ("tiku", "cover_rate"),
        ):
            with self.subTest(section=section, key=key):
                with self.assertRaises(ValueError):
                    self.load_ini(f"[{section}]\n{key}=invalid\n")

    def test_boolean_semantics(self):
        for value in (True, "1", "true", "YES", " y ", "On", 1):
            with self.subTest(value=value):
                self.assertIs(str_to_bool(value), True)
        for value in (False, "0", "false", "no", "off", "", "invalid", None, 2):
            with self.subTest(value=value):
                self.assertIs(str_to_bool(value), False)

    def test_course_list_filters_empty_items(self):
        for value, expected in (("a, ,b,,", ["a", "b"]), (" , , ", []), ("", [])):
            with self.subTest(value=value):
                common, _, _ = self.load_ini(f"[common]\ncourse_list={value}\n")
                self.assertEqual(common["course_list"], expected)
        common, _, _ = build_config_from_args(parse_args(["-l", " a, ,b,, "]))
        self.assertEqual(common["course_list"], ["a", "b"])

    def test_cli_zero_interval_is_preserved(self):
        common, tiku, notification, path = init_config(["--retry-interval", "0"])
        self.assertEqual(common["retry_interval"], 0.0)
        self.assertIsInstance(common["retry_interval"], float)
        self.assertEqual((tiku, notification, path), ({}, {}, None))


    def test_file_configuration_takes_precedence_without_cli_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.ini"
            path.write_text("[common]\nusername=file-user\nretry_interval=2.5\n", encoding="utf8")
            common, tiku, notification, config_path = init_config([
                "--config", str(path), "--username", "cli-user",
                "--retry-interval", "0", "--use-cookies", "--jobs", "8",
            ])
        self.assertEqual(common, {
            "username": "file-user", "retry_interval": 2.5,
            "notopen_action": "retry", "work_max_retries": 3,
        })
        self.assertEqual((tiku, notification, config_path), ({}, {}, str(path)))

    def test_help_uses_argparse_with_other_arguments(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as caught:
            parse_args(["--username", "user", "--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("--retry-interval", output.getvalue())


if __name__ == "__main__":
    unittest.main()
