# -*- coding: utf-8 -*-
"""章节重试、队列生命周期及异常传播的无网络回归测试。"""
import threading
import unittest
from unittest.mock import patch

from chaoxing_app import jobs as main


class DummyChaoxing:
    """仅提供 process_chapter 所需的最小接口，不发任何网络请求。"""

    def __init__(self, job_info):
        self.job_info = job_info
        self.rate_limiter = _NoopRateLimiter()

    def get_job_list(self, course, point):
        return self.job_info["jobs"], self.job_info["job_info"]


class _NoopRateLimiter:
    def limit_rate(self, *args, **kwargs):
        return None


class JobProcessorTestCase(unittest.TestCase):
    def setUp(self):
        main.logger.remove()

    def _make_processor(self, job_info, notopen_action="retry", max_tries=3):
        course = {"title": "课程"}
        point = {"title": "章节", "has_finished": False}
        task = main.ChapterTask(index=0, point=point, course=course)
        config = {
            "speed": 1.0,
            "jobs": 1,
            "notopen_action": notopen_action,
            "retry_interval": 0.01,
        }
        processor = main.JobProcessor(DummyChaoxing(job_info), [task], config)
        processor.max_tries = max_tries
        return processor, task

    def _run_with_timeout(self, processor, timeout=5.0):
        """对死锁给出有限等待，并在调用线程重新抛出 run 的异常。"""
        exception = {}

        def target():
            try:
                processor.run()
            except BaseException as exc:
                exception["exc"] = exc

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout)
        self.assertFalse(thread.is_alive(), f"JobProcessor.run() 超过 {timeout}s 未返回")
        for worker in processor.threads:
            self.assertFalse(worker.is_alive(), worker.name)
            self.assertFalse(worker.daemon, worker.name)
        for queue in (processor.task_queue, processor.retry_queue):
            self.assertTrue(queue.is_shutdown)
            self.assertTrue(queue.empty())
            self.assertEqual(queue.unfinished_tasks, 0)
        if exception:
            raise exception["exc"]

    def _not_open_job_info(self):
        return {"jobs": [], "job_info": {"notOpen": True}}

    def _error_job_info(self):
        return {"jobs": [{"type": "unknown"}], "job_info": {}}

    def test_not_open_stops_after_max_tries(self):
        processor, task = self._make_processor(self._not_open_job_info())
        self._run_with_timeout(processor)
        self.assertEqual(task.tries, 3)
        self.assertEqual(task.result, main.ChapterResult.NOT_OPEN)
        self.assertEqual(processor.failed_tasks, [])

    def test_not_open_continue_skips_without_retry(self):
        processor, task = self._make_processor(
            self._not_open_job_info(), notopen_action="continue"
        )
        self._run_with_timeout(processor)
        self.assertEqual(task.tries, 0)
        self.assertEqual(task.result, main.ChapterResult.NOT_OPEN)
        self.assertEqual(processor.failed_tasks, [])

    def test_error_retry_behavior_unchanged(self):
        processor, task = self._make_processor(self._error_job_info(), max_tries=5)
        self._run_with_timeout(processor)
        self.assertEqual(task.tries, 5)
        self.assertEqual(task.result, main.ChapterResult.ERROR)
        self.assertEqual(processor.failed_tasks, [task])

    def test_success_does_not_retry_and_stops_idle_retry_thread(self):
        processor, task = self._make_processor(self._not_open_job_info())
        task.point["has_finished"] = True
        self._run_with_timeout(processor)
        self.assertEqual(task.tries, 0)
        self.assertEqual(task.result, main.ChapterResult.SUCCESS)

    def test_completion_interrupts_retry_interval(self):
        processor, task = self._make_processor(self._error_job_info(), max_tries=2)
        processor.retry_interval = 60
        self._run_with_timeout(processor)
        self.assertEqual(task.tries, 2)
        self.assertEqual(processor.failed_tasks, [task])

    def test_worker_exception_propagates_with_pending_tasks(self):
        for error in (RuntimeError("worker failed"), SystemExit("worker exited")):
            with self.subTest(error=type(error).__name__):
                processor, task = self._make_processor(self._not_open_job_info())
                processor.tasks.extend(
                    main.ChapterTask(index=index, point=dict(task.point), course=task.course)
                    for index in range(1, 4)
                )
                with patch.object(main, "process_chapter", side_effect=error):
                    with self.assertRaises(type(error)) as caught:
                        self._run_with_timeout(processor)
                self.assertIs(caught.exception, error)
                self.assertEqual(task.tries, 0)
                self.assertEqual(processor.failed_tasks, [])

    def test_retry_thread_exception_propagates(self):
        processor, _ = self._make_processor(self._error_job_info())
        error = RuntimeError("retry failed")
        with patch.object(processor, "retry_thread", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                self._run_with_timeout(processor)
        self.assertIs(caught.exception, error)

    def test_empty_tasks_stop_all_threads(self):
        processor, _ = self._make_processor(self._not_open_job_info())
        processor.tasks.clear()
        self._run_with_timeout(processor)
        self.assertEqual(processor.failed_tasks, [])

    def test_default_workers_do_not_mutate_config(self):
        for jobs in (None, 0):
            with self.subTest(jobs=jobs):
                config = {"speed": 1.0, "notopen_action": "retry"}
                if jobs == 0:
                    config["jobs"] = jobs
                original = dict(config)
                processor = main.JobProcessor(DummyChaoxing(self._not_open_job_info()), [], config)
                self._run_with_timeout(processor)
                self.assertEqual(config, original)

    def test_chapter_executes_every_job_before_reporting_failure(self):
        jobs = [{"type": "document", "jobid": "first"}, {"type": "read", "jobid": "second"}]
        processor, task = self._make_processor({"jobs": jobs, "job_info": {}})
        with patch.object(main, "process_job", side_effect=[main.StudyResult.ERROR, main.StudyResult.SUCCESS]) as process:
            result = main.process_chapter(processor.chaoxing, task.course, task.point, processor.speed)
        self.assertEqual(result, main.ChapterResult.ERROR)
        self.assertEqual(process.call_count, 2)
        self.assertEqual([call.args[2] for call in process.call_args_list], jobs)

    def test_chapter_without_jobs_succeeds(self):
        processor, task = self._make_processor({"jobs": [], "job_info": {}})
        self._run_with_timeout(processor)
        self.assertEqual(task.result, main.ChapterResult.SUCCESS)
        self.assertEqual(task.tries, 0)

class LiveJobResultTest(unittest.TestCase):
    """直播任务失败必须向外传播, 不能再被记为 SUCCESS。"""

    class _LiveChaoxing(DummyChaoxing):
        def get_uid(self):
            return "uid"

    def _job(self):
        return {"type": "live", "jobid": "live-1"}

    def _run(self, run_live_return):
        job = self._job()
        chaoxing = self._LiveChaoxing({"jobs": [job], "job_info": {"knowledgeid": "k"}})
        with patch.object(main.LiveProcessor, "run_live", return_value=run_live_return) as run_live:
            result = main.process_job(
                chaoxing,
                {"title": "课程", "clazzId": "1", "courseId": "2"},
                job,
                {"knowledgeid": "k"},
                1.0,
            )
        self.assertEqual(run_live.call_count, 1)
        return result

    def test_live_failure_returns_error(self):
        self.assertEqual(self._run(False), main.StudyResult.ERROR)

    def test_live_success_returns_success(self):
        self.assertEqual(self._run(True), main.StudyResult.SUCCESS)


if __name__ == "__main__":
    unittest.main()
