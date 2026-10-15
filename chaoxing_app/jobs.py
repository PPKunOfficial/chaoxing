"""章节任务执行与有界重试。"""

import enum
import threading
import traceback
from dataclasses import dataclass
from functools import wraps
from queue import PriorityQueue, ShutDown
from typing import Any

from api.base import Chaoxing, StudyResult
from api.live import Live
from api.live_process import LiveProcessor
from api.logger import logger


class ChapterResult(enum.Enum):
    SUCCESS = 0,
    ERROR = 1,
    NOT_OPEN = 2,
    PENDING = 3


def log_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseException as exc:
            logger.error(f"Error in thread {threading.current_thread().name}: {exc}")
            traceback.print_exception(type(exc), exc, exc.__traceback__)
            raise

    return wrapper


def process_job(chaoxing: Chaoxing, course: dict, job: dict, job_info: dict, speed: float) -> StudyResult:
    """处理单个任务点。"""
    if job["type"] == "video":
        logger.trace(f"识别到视频任务, 任务章节: {course['title']} 任务ID: {job['jobid']}")
        # 超星的接口没有返回当前任务是否为 Audio 音频任务。
        video_result = chaoxing.study_video(
            course, job, job_info, _speed=speed, _type="Video"
        )
        if video_result.is_failure():
            logger.warning("当前任务非视频任务, 正在尝试音频任务解码")
            video_result = chaoxing.study_video(
                course, job, job_info, _speed=speed, _type="Audio")
        if video_result.is_failure():
            logger.warning(
                f"出现异常任务 -> 任务章节: {course['title']} 任务ID: {job['jobid']}, 已跳过"
            )
        return video_result
    elif job["type"] == "document":
        logger.trace(f"识别到文档任务, 任务章节: {course['title']} 任务ID: {job['jobid']}")
        return chaoxing.study_document(course, job)
    elif job["type"] == "workid":
        logger.trace(f"识别到章节检测任务, 任务章节: {course['title']}")
        return chaoxing.study_work(course, job, job_info)
    elif job["type"] == "read":
        logger.trace(f"识别到阅读任务, 任务章节: {course['title']}")
        return chaoxing.study_read(course, job, job_info)
    elif job["type"] == "live":
        logger.trace(f"识别到直播任务, 任务章节: {course['title']} 任务ID: {job['jobid']}")
        try:
            defaults = {
                "userid": chaoxing.get_uid(),
                "clazzId": course.get("clazzId"),
                "knowledgeid": job_info.get("knowledgeid"),
            }
            live = Live(
                attachment=job,
                defaults=defaults,
                course_id=course.get("courseId"),
            )
            # 调用方已等待直播完成，无需再创建一个立即 join 的线程。
            # 失败必须向外传播: 以前丢弃返回值会让未完成的直播也被记为成功
            if not LiveProcessor.run_live(live, speed):
                logger.error("直播任务未完成，返回失败以交给章节重试")
                return StudyResult.ERROR
            return StudyResult.SUCCESS
        except Exception as exc:
            logger.error(f"处理直播任务时出错: {exc}")
            return StudyResult.ERROR

    logger.error(f"未知任务类型: {job['type']}")
    return StudyResult.ERROR


@dataclass
class ChapterTask:
    index: int
    point: dict[str, Any]
    course: dict[str, Any]
    result: ChapterResult = ChapterResult.PENDING
    tries: int = 0

    def __lt__(self, other):
        """比较两个任务的索引大小，用于优先级队列排序。"""
        if not isinstance(other, ChapterTask):
            return NotImplemented
        return self.index < other.index


class JobProcessor:
    def __init__(self, chaoxing: Chaoxing, tasks: list[ChapterTask], config: dict[str, Any]):
        """初始化任务处理器，不修改调用方的配置。"""
        self.chaoxing = chaoxing
        self.speed = config["speed"]
        self.max_tries = 5
        self.tasks = tasks
        self.failed_tasks: list[ChapterTask] = []
        self.task_queue: PriorityQueue[ChapterTask] = PriorityQueue()
        self.retry_queue: PriorityQueue[ChapterTask] = PriorityQueue()
        self.threads: list[threading.Thread] = []
        self.worker_num = config.get("jobs") or 4
        self.config = dict(config)
        # `ask` 尚未实现真正的询问, 与 retry 同分支; 明确提示而不是静默按重试处理
        if self.config.get("notopen_action") == "ask":
            logger.warning("notopen_action=ask 目前与 retry 同一分支, 将按重试处理, 不会询问")
        self.retry_interval = config.get("retry_interval", 1.0)
        self._condition = threading.Condition()
        self._pending = 0
        self._error: BaseException | None = None
        self._stop = threading.Event()

    def run(self):
        """等待全部章节完成，关闭两条队列并回收线程，再传播首个线程异常。"""
        completed = False
        try:
            self._pending = len(self.tasks)
            for task in self.tasks:
                self.task_queue.put(task)

            targets = [self.worker_thread] * self.worker_num + [self.retry_thread]
            for index, target in enumerate(targets):
                thread = threading.Thread(
                    target=self._run_thread,
                    args=(target,),
                    name=f"chaoxing-job-{index}",
                    daemon=False,
                )
                thread.start()
                self.threads.append(thread)

            with self._condition:
                # 队列间转移时可能暂时为空，使用逻辑章节数跟踪整个生命周期。
                self._condition.wait_for(lambda: self._pending == 0 or self._error is not None)
                completed = self._error is None
        finally:
            self._stop.set()
            self.task_queue.shutdown(immediate=not completed)
            self.retry_queue.shutdown(immediate=not completed)
            for thread in self.threads:
                thread.join()

        if self._error is not None:
            raise self._error

    def _run_thread(self, target):
        try:
            target()
        except BaseException as exc:
            with self._condition:
                if self._error is None:
                    self._error = exc
                self._condition.notify_all()

    @log_error
    def worker_thread(self):
        while True:
            try:
                task = self.task_queue.get()
            except ShutDown:
                return
            try:
                finished = self._process_task(task)
            finally:
                self.task_queue.task_done()
            if finished:
                with self._condition:
                    self._pending -= 1
                    self._condition.notify_all()

    def _process_task(self, task):
        task.result = process_chapter(self.chaoxing, task.course, task.point, self.speed)
        match task.result:
            case ChapterResult.SUCCESS:
                logger.debug("Task success: {} - {}", task.course["title"], task.point["title"])
            case ChapterResult.NOT_OPEN:
                if self.config["notopen_action"] == "continue":
                    logger.warning("章节未开启: {} - {}, 正在跳过", task.course["title"], task.point["title"])
                    return True
                task.tries += 1
                if task.tries >= self.max_tries:
                    logger.error(
                        "章节未开启: {} - {} 可能由于上一章节的章节检测未完成, 也可能由于该章节因为时效已关闭，"
                        "请手动检查完成并提交再重试。或者在配置中配置(自动跳过关闭章节/开启题库并启用提交)",
                        task.course["title"], task.point["title"],
                    )
                    return True
                self.retry_queue.put(task)
                return False
            case ChapterResult.ERROR:
                task.tries += 1
                logger.warning("重试任务 {} - {} ({}/{} 次尝试)", task.course["title"], task.point["title"],
                               task.tries, self.max_tries)
                if task.tries >= self.max_tries:
                    logger.error("任务重试次数达到上限: {} - {}", task.course["title"], task.point["title"])
                    self.failed_tasks.append(task)
                    return True
                self.retry_queue.put(task)
                return False
            case _:
                logger.error("任务 {} 的状态无效 {}", task.result, task.point["title"])
                self.failed_tasks.append(task)
        return True

    @log_error
    def retry_thread(self):
        while True:
            try:
                task = self.retry_queue.get()
            except ShutDown:
                return
            try:
                try:
                    self.task_queue.put(task)
                except ShutDown:
                    if self._stop.is_set():
                        return
                    raise
                # 保留原有重试间隔，同时允许 run 在完成或异常时立即唤醒。
                self._stop.wait(self.retry_interval)
            finally:
                self.retry_queue.task_done()


def process_chapter(chaoxing: Chaoxing, course: dict[str, Any], point: dict[str, Any], speed: float) -> ChapterResult:
    """执行章节的全部任务点后汇总结果。"""
    logger.info(f'当前章节: {point["title"]}')
    if point["has_finished"]:
        logger.info(f'章节：{point["title"]} 已完成所有任务点')
        return ChapterResult.SUCCESS

    chaoxing.rate_limiter.limit_rate(random_time=True, random_min=0, random_max=0.2)
    jobs, job_info = chaoxing.get_job_list(course, point)
    if job_info.get("notOpen", False):
        return ChapterResult.NOT_OPEN

    job_results = [process_job(chaoxing, course, job, job_info, speed) for job in jobs]
    if any(result.is_failure() for result in job_results):
        return ChapterResult.ERROR
    return ChapterResult.SUCCESS
