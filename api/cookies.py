# -*- coding: utf-8 -*-
"""Cookie 文件读写。

持久化格式为 `name=value;name=value`：value 中允许出现 `=`，解析时只按首个
`=` 切分，因此编码与解码必须成对保持该文本协议。
"""
import os.path
import threading

import requests

from api.config import GlobalConst as gc

# 定义全局 Cookie 文件锁，保证读写绝对安全
cookie_lock = threading.RLock()


def save_cookies(session: requests.Session) -> None:
    with cookie_lock:
        buffer = ";".join(f"{k}={v}" for k, v in session.cookies.items())
        with open(gc.COOKIES_PATH, "w") as f:
            f.write(buffer)


def use_cookies() -> dict:
    with cookie_lock:
        if not os.path.exists(gc.COOKIES_PATH):
            return {}

        cookies = {}
        try:
            with open(gc.COOKIES_PATH, "r") as f:
                buffer = f.read().strip()
                if not buffer:
                    return {}
                for item in buffer.split(";"):
                    item = item.strip()
                    if not item:
                        continue
                    parts = item.split("=", 1)
                    if len(parts) == 2:
                        cookies[parts[0]] = parts[1]
        except Exception:
            return {}

        return cookies
