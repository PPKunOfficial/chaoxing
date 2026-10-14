# -*- coding: utf-8 -*-
"""题库包：查询核心、缓存、回退链、注册表与各 provider 实现。

调用方按职责从子模块导入（如 `api.answer.registry`、`api.answer.core`），
本模块不再导出符号，避免形成旧 `api.answer` 模块的兼容壳。
"""
