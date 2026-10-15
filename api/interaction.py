"""终端交互状态，不依赖题库、日志或平台客户端。

沿用进程内唯一的非重入锁：手动 provider 在输入期间持锁，日志和视频
只查询状态。锁释放本身不冲刷日志；下一条日志触发既有缓冲输出。
"""
from threading import Lock

manual_input_lock = Lock()


def is_manual_input_active() -> bool:
    """是否有手动输入占用终端（跨 provider 实例共享）。"""
    return manual_input_lock.locked()
