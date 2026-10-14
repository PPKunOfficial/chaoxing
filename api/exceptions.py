# -*- coding: utf-8 -*-
"""领域异常。

各异常不额外定义构造器：调用方只依赖消息与类型，父类行为已足够。
"""


class LoginError(Exception):
    """登录失败。"""


class InputFormatError(Exception):
    """用户输入格式不合法。"""


class MaxRollBackExceeded(Exception):
    """测验重做次数超过上限。"""


class MaxRetryExceeded(Exception):
    """请求或任务重试次数超过上限。"""


class FontDecodeError(Exception):
    """字体映射缺失或解码失败。"""
