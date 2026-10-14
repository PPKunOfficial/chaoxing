"""命令行编排：配置、登录、课程选择和任务执行。"""

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any

from .config import init_config, str_to_bool


def init_chaoxing(common_config, tiku_config, config_path=None):
    from api.answer import Tiku
    from api.base import Account, Chaoxing
    from api.logger import logger

    username = common_config.get("username", "")
    password = common_config.get("password", "")
    if (not username or not password) and not common_config.get("use_cookies", False):
        username = input("请输入你的手机号, 按回车确认\n手机号:")
        password = input("请输入你的密码, 按回车确认\n密码:")

    tiku = Tiku.get_tiku_from_config(tiku_config, config_path=config_path)
    tiku.init_tiku()
    provider = tiku_config.get("provider", "")
    providers = {name.strip() for name in provider.split(",")}
    if providers & {"AI", "SiliconFlow"}:
        if tiku_config.get("check_llm_connection", "true").lower() == "true":
            logger.info("正在验证大模型配置 (provider={})...", provider)
            if not tiku.check_llm_connection():
                logger.error("大模型连接检查失败")
                choice = input("大模型连接检查失败，无法准确答题，是否继续运行？(Y/n): ").strip().lower()
                if choice not in {"", "y", "yes"}:
                    raise RuntimeError("用户取消运行")
                logger.info("用户选择继续运行...")

    return Chaoxing(
        account=Account(username, password),
        tiku=tiku,
        query_delay=tiku_config.get("delay", 0),
        work_max_retries=common_config.get("work_max_retries", 3),
        work_redo_enabled=common_config.get("work_redo_enabled", False),
    )


def filter_courses(all_course: list[dict[str, Any]], course_list: Sequence[str] | None):
    """按课程和班级去重筛选；留空或未匹配时保持学习全部课程的约定。"""
    if not course_list:
        print("*" * 10 + "课程列表" + "*" * 10)
        for course in all_course:
            print(f"ID: {course['courseId']} 班级ID: {course['clazzId']} 课程名: {course['title']}")
        print("*" * 28)
        print("提示: 同一 courseId 下若存在多个班级, 将分别完成。")
        course_list = input("请输入想要学习的课程列表,以逗号分隔,例: 2151141,189191,198198\n").split(",")

    selected_ids = {item.strip() for item in course_list if item.strip()}
    selected = []
    seen = set()
    for course in all_course:
        key = (course["courseId"], course["clazzId"])
        if course["courseId"] in selected_ids and key not in seen:
            selected.append(course)
            seen.add(key)
    return selected or all_course


def format_time(num, suffix="", divisor="") -> str:
    """适配 tqdm.format_sizeof 的调用签名，将秒数展示为时长。"""
    hours, remainder = divmod(round(num), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


@contextmanager
def progress_time_format():
    from tqdm import tqdm

    previous = tqdm.format_sizeof
    tqdm.format_sizeof = format_time
    try:
        yield
    finally:
        tqdm.format_sizeof = previous


def run_courses(chaoxing, courses, config) -> None:
    from api.logger import logger
    from .jobs import ChapterTask, JobProcessor

    with progress_time_format():
        tasks = []
        for course in courses:
            logger.info("正在读取课程章节: {}", course["title"])
            points = chaoxing.get_course_point(course["courseId"], course["clazzId"], course["cpi"])
            tasks.extend(
                ChapterTask(index=index, point=point, course=course)
                for index, point in enumerate(points["points"])
            )
        JobProcessor(chaoxing, tasks, config).run()


def main(argv: Sequence[str] | None = None) -> None:
    # 先解析参数，--help 不必加载网络、OCR 与字体依赖。
    common, tiku_config, notification_config, config_path = init_config(argv)

    from api.exceptions import LoginError
    from api.logger import logger
    from api.notification import NotificationFactory
    from api.process import increase_learning_count_for_course

    notification = None
    try:
        common["speed"] = min(2.0, max(1.0, common.get("speed", 1.0)))
        common.setdefault("notopen_action", "retry")
        chaoxing = init_chaoxing(common, tiku_config, config_path=config_path)
        notification = NotificationFactory.create_service(notification_config)
        login_state = chaoxing.login(login_with_cookies=common.get("use_cookies", False))
        if not login_state["status"]:
            raise LoginError(login_state["msg"])

        courses = filter_courses(chaoxing.get_course_list(), common.get("course_list"))
        logger.info("课程列表过滤完毕, 当前课程任务数量: {}", len(courses))
        run_courses(chaoxing, courses, common)
        logger.info("所有课程学习任务已完成")
        notification.send("chaoxing : 所有课程学习任务已完成")

        if str_to_bool(common.get("add_learning_count", False)):
            logger.info("刷课完成，开始增加章节学习次数...")
            common["target_count"] = int(common.get("target_count", 100))
            for course in courses:
                increase_learning_count_for_course(chaoxing, course, common)
            logger.info("所有课程章节学习次数增加完成")
            notification.send("chaoxing : 所有课程章节学习次数增加完成")
    except KeyboardInterrupt:
        logger.error("错误: 程序被用户手动中断")
    except Exception as exc:
        import traceback

        detail = traceback.format_exc()
        logger.error("错误: {}: {}\n{}", type(exc).__name__, exc, detail)
        if notification is not None:
            try:
                notification.send(f"chaoxing : 出现错误 {type(exc).__name__}: {exc}\n{detail}")
            except Exception:
                logger.exception("发送错误通知失败")
        raise
