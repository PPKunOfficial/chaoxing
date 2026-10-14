"""命令行参数与 INI 配置解析，不依赖网络或 API 模块。"""

import argparse
import configparser
from collections.abc import Sequence
from os import PathLike
from typing import Any


__all__ = [
    "parse_args",
    "load_config_from_file",
    "build_config_from_args",
    "init_config",
    "str_to_bool",
]


def str_to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """解析参数；argv 为 None 时读取进程命令行。"""
    parser = argparse.ArgumentParser(
        description="Samueli924/chaoxing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--use-cookies", action="store_true", help="使用cookies登录")
    parser.add_argument(
        "-c", "--config", type=str, default=None, help="使用配置文件运行程序"
    )
    parser.add_argument("-u", "--username", type=str, default=None, help="手机号账号")
    parser.add_argument("-p", "--password", type=str, default=None, help="登录密码")
    parser.add_argument(
        "-l", "--list", type=str, default=None, help="要学习的课程ID列表, 以 , 分隔"
    )
    parser.add_argument(
        "-s", "--speed", type=float, default=1.0, help="视频播放倍速 (默认1, 最大2)"
    )
    parser.add_argument(
        "-j", "--jobs", type=int, default=4,
        help="同时进行的章节数 (默认4, 如果一个章节有多个任务点，不会限制同时处理任务点的数量)",
    )
    parser.add_argument(
        "-v", "--verbose", "--debug", action="store_true",
        help="启用调试模式, 输出DEBUG级别日志",
    )
    parser.add_argument(
        "-a", "--notopen-action", type=str, default="retry",
        choices=["retry", "ask", "continue"],
        help="遇到关闭任务点时的行为: retry-重试, ask-询问, continue-继续",
    )
    parser.add_argument("--auto-sign", action="store_true", help="自动签到")
    parser.add_argument(
        "--retry-interval", type=float, default=1.0,
        help="重试等待时间, 单位秒 (默认1.0)",
    )
    parser.add_argument(
        "-lc", "--add-learning-count", action="store_true",
        help="开启章节学习次数增加模式",
    )
    parser.add_argument(
        "-tc", "--target-count", type=int, default=100,
        help="章节学习次数目标总次数 (默认100)",
    )
    return parser.parse_args(argv)


def load_config_from_file(
    config_path: str | PathLike[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """读取原有配置字段，仅转换约定的数值、布尔与课程列表字段。"""
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf8")
    sections: list[dict[str, Any]] = [
        dict(config.items(name)) if config.has_section(name) else {}
        for name in ("common", "tiku", "notification")
    ]
    common_config, tiku_config, notification_config = sections

    if config.has_section("common"):
        if "course_list" in common_config:
            common_config["course_list"] = [
                item.strip() for item in common_config["course_list"].split(",")
                if item.strip()
            ]
        for key, default in (
            ("notopen_action", "retry"),
            ("retry_interval", 1.0),
            ("work_max_retries", 3),
        ):
            common_config.setdefault(key, default)
        for key, convert in (
            ("speed", float),
            ("jobs", int),
            ("retry_interval", float),
            ("target_count", int),
            ("work_redo_enabled", str_to_bool),
            ("use_cookies", str_to_bool),
            ("add_learning_count", str_to_bool),
        ):
            if key in common_config:
                common_config[key] = convert(common_config[key])
        try:
            common_config["work_max_retries"] = int(common_config["work_max_retries"])
        except ValueError:
            common_config["work_max_retries"] = 3
        for key in ("username", "password"):
            if key in common_config and common_config[key] is not None:
                common_config[key] = common_config[key].strip()

    for key in ("delay", "cover_rate"):
        if key in tiku_config:
            tiku_config[key] = float(tiku_config[key])
    return common_config, tiku_config, notification_config


def build_config_from_args(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """从命令行参数构建配置，不将零重试间隔替换为默认值。"""
    common_config = {
        "use_cookies": args.use_cookies,
        "username": args.username,
        "password": args.password,
        "course_list": [
            item.strip() for item in args.list.split(",") if item.strip()
        ] if args.list else None,
        "speed": args.speed or 1.0,
        "jobs": args.jobs,
        "notopen_action": args.notopen_action or "retry",
        "retry_interval": args.retry_interval,
        "add_learning_count": args.add_learning_count,
        "target_count": args.target_count,
    }
    return common_config, {}, {}


def init_config(
    argv: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None]:
    """配置文件存在于参数时，使用文件配置而不合并其他 CLI 设置。"""
    args = parse_args(argv)
    if args.config:
        configs = load_config_from_file(args.config)
    else:
        configs = build_config_from_args(args)
    return *configs, args.config
