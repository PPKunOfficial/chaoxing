# -*- coding: utf-8 -*-
"""Cookie 文件文本协议回归：value 含 `=` 时读写必须保持不变。"""
import os
import tempfile
import unittest
from unittest.mock import patch

from requests.cookies import cookiejar_from_dict

from api.config import GlobalConst as gc
from api.cookies import save_cookies, use_cookies


class CookieFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "cookies.txt")
        patcher = patch.object(gc, "COOKIES_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def test_value_containing_equals_is_preserved(self):
        self._write("uid=1;token=abc=def=;plain=x")
        self.assertEqual(use_cookies(), {"uid": "1", "token": "abc=def=", "plain": "x"})

    def test_save_then_use_round_trip(self):
        class _Session:
            pass

        session = _Session()
        session.cookies = cookiejar_from_dict({"uid": "1", "token": "a=b"})
        save_cookies(session)
        with open(self.path) as f:
            self.assertEqual(f.read(), "uid=1;token=a=b")
        self.assertEqual(use_cookies(), {"uid": "1", "token": "a=b"})

    def test_missing_and_empty_and_broken_file_return_empty(self):
        self.assertEqual(use_cookies(), {})
        self._write("")
        self.assertEqual(use_cookies(), {})
        self._write("   \n ")
        self.assertEqual(use_cookies(), {})

    def test_entries_without_equals_are_skipped(self):
        self._write("uid=1;broken;token=x")
        self.assertEqual(use_cookies(), {"uid": "1", "token": "x"})

    def test_save_writes_empty_file_for_no_cookies(self):
        class _Session:
            pass

        session = _Session()
        session.cookies = cookiejar_from_dict({})
        save_cookies(session)
        with open(self.path) as f:
            self.assertEqual(f.read(), "")
        save_cookies(session)
        with open(self.path) as f:
            self.assertEqual(f.read(), "")
        self.assertEqual(use_cookies(), {})


if __name__ == "__main__":
    unittest.main()
