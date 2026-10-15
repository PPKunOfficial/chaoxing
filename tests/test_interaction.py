"""交互解耦回归：共享锁、真实输入、日志缓冲和视频展示调用路径。"""
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from api.answer.providers.manual import TikuManual
from api.base import Chaoxing, StudyResult
from api.interaction import is_manual_input_active, manual_input_lock
from api.logger import MAX_LOG_BUFFER_SIZE, log_buffer, logger, tqdm_sink

QUESTION = {"id": "101", "title": "合成题", "type": "single", "options": "A、甲\nB、乙"}


class InteractionTest(unittest.TestCase):
    def setUp(self):
        logger.complete()  # 排空前一测试的异步日志，避免干扰 sink 断言
        self.assertFalse(is_manual_input_active())
        log_buffer.clear()
        self.addCleanup(log_buffer.clear)

    def test_state_tracks_non_reentrant_lock(self):
        with manual_input_lock:
            self.assertTrue(is_manual_input_active())
            self.assertFalse(manual_input_lock.acquire(blocking=False))
        self.assertFalse(is_manual_input_active())

    def test_buffer_order_and_next_message_flush_timing(self):
        with patch("api.logger.tqdm.write") as write, patch("api.logger.tqdm_stream") as stream:
            with manual_input_lock:
                tqdm_sink("first\n")
                tqdm_sink("second\n")
                self.assertEqual(log_buffer, ["first\n", "second\n"])
                write.assert_not_called()
            # 解锁本身不输出，不提前变成自动冲刷
            write.assert_not_called()
            self.assertEqual(log_buffer, ["first\n", "second\n"])
            tqdm_sink("after\n")
            self.assertEqual(write.call_args_list, [call(s, file=stream) for s in ("first", "second", "after")])
            self.assertEqual(log_buffer, [])
            self.assertEqual(stream.flush.call_count, 3)

    def test_buffer_limit_keeps_first_1000_messages(self):
        self.assertEqual(MAX_LOG_BUFFER_SIZE, 1000)
        with patch("api.logger.tqdm.write") as write, patch("api.logger.tqdm_stream") as stream:
            with manual_input_lock:
                for i in range(1002):
                    tqdm_sink(str(i))
                self.assertEqual(log_buffer, [str(i) for i in range(1000)])
                write.assert_not_called()
            tqdm_sink("after")
            self.assertEqual(write.call_args_list, [call(str(i), file=stream) for i in range(1000)] +
                             [call("after", file=stream)])
            self.assertEqual(log_buffer, [])

    def test_single_input_uses_shared_state_and_flushes_after_return(self):
        manual = TikuManual()
        with patch.object(manual, "_safe_close_tqdm_bars"), patch("builtins.print"), \
                patch("api.answer.providers.manual.logger") as manual_logger, \
                patch("api.logger.tqdm.write") as write, patch("api.logger.tqdm_stream") as stream:
            def answer(_):
                self.assertTrue(is_manual_input_active())
                tqdm_sink("background")
                write.assert_not_called()
                return "A"

            manual_logger.debug.side_effect = lambda _: tqdm_sink("input-finished")
            with patch("builtins.input", side_effect=answer):
                self.assertEqual(manual._query(QUESTION), "A")
            self.assertFalse(is_manual_input_active())
            self.assertEqual(write.call_args_list, [call("background", file=stream), call("input-finished", file=stream)])

    def test_batch_input_and_confirmation_both_hold_shared_lock(self):
        manual = TikuManual()
        manual.separator = ";"
        inputs = iter(["A;B", "y"])

        def answer(_):
            self.assertTrue(is_manual_input_active())
            return next(inputs)

        with patch.object(manual, "_safe_close_tqdm_bars"), patch("builtins.print"), \
                patch("api.answer.providers.manual.logger"), patch("builtins.input", side_effect=answer):
            self.assertEqual(manual._query_all([QUESTION, QUESTION]), ["A", "B"])
        self.assertFalse(is_manual_input_active())

    def test_input_exception_releases_lock_for_single_and_batch(self):
        for batch in (False, True):
            with self.subTest(batch=batch):
                manual = TikuManual()
                manual.separator = ";"
                with patch.object(manual, "_safe_close_tqdm_bars"), patch("builtins.print"), \
                        patch("api.answer.providers.manual.logger"), patch("builtins.input", side_effect=EOFError):
                    with self.assertRaises(EOFError):
                        manual._query_all([QUESTION]) if batch else manual._query(QUESTION)
                self.assertFalse(is_manual_input_active())
                self.assertTrue(manual_input_lock.acquire(blocking=False))
                manual_input_lock.release()

    def test_single_and_batch_instances_are_mutually_exclusive(self):
        first, second = TikuManual(), TikuManual()
        second.default_mode = "single"
        first_entered, second_attempted, second_entered, release = (threading.Event() for _ in range(4))
        answers, errors = [], []

        def close_bars():
            if threading.current_thread().name == "second-input":
                second_attempted.set()

        def answer(_):
            self.assertTrue(is_manual_input_active())
            if threading.current_thread().name == "first-input":
                first_entered.set()
                if not release.wait(2):
                    raise AssertionError("首次输入未收到释放信号")
            else:
                second_entered.set()
            return "A"

        def run(manual, batch):
            try:
                answers.append(manual._query_all([QUESTION]) if batch else manual._query(QUESTION))
            except BaseException as error:
                errors.append(error)

        threads = [threading.Thread(target=run, args=(first, False), name="first-input"),
                   threading.Thread(target=run, args=(second, True), name="second-input")]
        with patch.object(TikuManual, "_safe_close_tqdm_bars", side_effect=close_bars), \
                patch("builtins.print"), patch("api.answer.providers.manual.logger"), \
                patch("builtins.input", side_effect=answer):
            threads[0].start()
            try:
                self.assertTrue(first_entered.wait(2))
                threads[1].start()
                self.assertTrue(second_attempted.wait(2))
                self.assertFalse(second_entered.wait(0.05))
            finally:
                release.set()
                for thread in threads:
                    if thread.ident is not None:
                        thread.join(3)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertCountEqual(answers, ["A", ["A"]])
        self.assertTrue(second_entered.is_set())
        self.assertFalse(is_manual_input_active())

    def test_video_closes_and_restores_bars_using_shared_state(self):
        client = Chaoxing()
        client.get_fid = Mock(return_value="SYNTHETIC_FID")
        status = {"status": "success", "duration": 4, "dtoken": "SYNTHETIC_DTOKEN", "crc": "", "key": ""}
        session = SimpleNamespace(get=Mock(return_value=SimpleNamespace(json=lambda: status)))
        clock = [0]
        first_bar, second_bar = Mock(), Mock()
        events = []
        first_bar.close.side_effect = lambda: events.append("close-first")
        second_bar.close.side_effect = lambda: events.append("close-second")
        first_bar.refresh.side_effect = lambda: events.append("refresh-first")
        second_bar.refresh.side_effect = lambda: events.append("refresh-second")

        def sleep(_):
            clock[0] += 1
            if clock[0] == 1:
                manual_input_lock.acquire()
            elif clock[0] == 2:
                manual_input_lock.release()

        with patch("requests.sessions.Session.request", side_effect=AssertionError("禁止真实 HTTP")), \
                patch("api.base.SessionManager.get_session", return_value=session), patch("api.base.logger"), \
                patch("api.base.time.time", side_effect=lambda: clock[0]), patch("api.base.time.sleep", side_effect=sleep), \
                patch("api.base.random.uniform", return_value=30), \
                patch("api.base.tqdm", side_effect=[first_bar, second_bar]) as bars, \
                patch.object(client, "video_progress_log", side_effect=[(False, 200), (True, 200)]):
            try:
                result = client.study_video({}, {"objectid": "synthetic", "playTime": "0", "name": "合成视频"}, {})
            finally:
                if is_manual_input_active():
                    manual_input_lock.release()
        self.assertIs(result, StudyResult.SUCCESS)
        self.assertEqual(bars.call_count, 2)
        self.assertEqual([c.kwargs["initial"] for c in bars.call_args_list], [0, 2])
        first_bar.close.assert_called_once()
        second_bar.close.assert_called_once()
        self.assertEqual(events[:3], ["refresh-first", "close-first", "refresh-second"])
        self.assertEqual(events[-1], "close-second")

    def test_video_exception_still_closes_progress_bar(self):
        client = Chaoxing()
        client.get_fid = Mock(return_value="SYNTHETIC_FID")
        status = {"status": "success", "duration": 4, "dtoken": "SYNTHETIC_DTOKEN", "crc": "", "key": ""}
        session = SimpleNamespace(get=Mock(return_value=SimpleNamespace(json=lambda: status)))
        with patch("api.base.SessionManager.get_session", return_value=session), patch("api.base.logger"), \
                patch("api.base.time.time", return_value=0), patch("api.base.random.uniform", return_value=30), \
                patch("api.base.time.sleep", side_effect=RuntimeError("interrupted")), patch("api.base.tqdm") as bars, \
                patch.object(client, "video_progress_log", return_value=(False, 200)):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                client.study_video({}, {"objectid": "synthetic", "playTime": "0", "name": "合成视频"}, {})
        bars.return_value.close.assert_called_once()

    def test_imports_do_not_load_manual_provider(self):
        code = """
import sys
import api.interaction
assert not any(name in sys.modules for name in ('loguru', 'requests', 'tqdm'))
import api.logger
assert 'api.answer.providers.manual' not in sys.modules
import api.base
assert 'api.answer.providers.manual' not in sys.modules
print('independent interaction imports: OK')
"""
        root = str(Path(__file__).resolve().parents[1])
        env = os.environ | {"PYTHONPATH": root}
        with tempfile.TemporaryDirectory(dir=os.environ.get("PI_SCRATCH_DIR")) as directory:
            result = subprocess.run([sys.executable, "-c", code], cwd=directory, env=env,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("independent interaction imports: OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
