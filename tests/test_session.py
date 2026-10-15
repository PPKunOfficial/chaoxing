# -*- coding: utf-8 -*-
"""Session 生命周期回归：进程内单例、只构造一次、cookie 显式同步。

契约见 `.agents/api重构施工方案.md` 第四节「修复契约」。以前每次
`get_session()` 都会重建 Session（重读 cookie 文件、重设 header），
运行期内存态会被静默丢弃。
"""
import threading
import unittest
from unittest.mock import patch

from api.base import SessionManager


class SessionManagerTest(unittest.TestCase):
    def test_get_session_returns_the_same_object(self):
        self.assertIs(SessionManager.get_session(), SessionManager.get_session())

    def test_runtime_header_survives_repeated_access(self):
        session = SessionManager.get_session()
        session.headers["X-Probe-Session"] = "1"
        self.addCleanup(session.headers.pop, "X-Probe-Session", None)

        self.assertEqual(SessionManager.get_session().headers.get("X-Probe-Session"), "1")

    def test_session_is_constructed_only_once(self):
        """修复前每次获取都重建会话(顺带重读 cookie 文件), 用调用次数锁住该行为。"""
        SessionManager.get_session()
        with patch("api.base.use_cookies") as use_cookies:
            for _ in range(3):
                SessionManager.get_session()
            use_cookies.assert_not_called()

    def test_update_cookies_keeps_session_identity(self):
        session = SessionManager.get_session()
        SessionManager.update_cookies()
        self.assertIs(SessionManager.get_session(), session)

    def test_concurrent_access_yields_single_instance(self):
        sessions = []

        def grab():
            sessions.append(SessionManager.get_session())

        threads = [threading.Thread(target=grab) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(sessions), 8)
        self.assertEqual(len({id(session) for session in sessions}), 1)


if __name__ == "__main__":
    unittest.main()
