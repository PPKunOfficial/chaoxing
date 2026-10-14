# -*- coding: utf-8 -*-
"""题库注册表与构造入口：provider 名称表、空题库与按配置装配。

provider 名称与配置中的字符串一一对应，也是回退顺序的来源；新增题库需要
同时在此登记，否则配置会被判定为无效。
"""
import configparser
from typing import Optional

from api.answer.core import Tiku
from api.answer.fallback import TikuFallback
from api.answer.providers.ai import AI
from api.answer.providers.manual import TikuManual
from api.answer.providers.siliconflow import SiliconFlow
from api.answer.providers.traditional import TikuAdapter, TikuGo, TikuLike, TikuYanxi
from api.logger import logger


class DummyTiku(Tiku):
    def __init__(self, config_path: Optional[str] = None) -> None:
        """初始化空题库."""
        super().__init__(config_path)
        self.name = '空/禁用题库'
        self.DISABLE = True

    def _query(self, q_info: dict) -> Optional[str]:
        return None


PROVIDER_REGISTRY = {
    'TikuYanxi': TikuYanxi,
    'TikuGo': TikuGo,
    'TikuLike': TikuLike,
    'TikuAdapter': TikuAdapter,
    'AI': AI,
    'SiliconFlow': SiliconFlow,
    'TikuManual': TikuManual,
}


def get_tiku_from_config(config: Optional[dict] = None, config_path: Optional[str] = None):
    """
    从配置文件加载题库, 这个配置可以是用户提供, 可以是默认配置文件
    """
    conf = config
    path = config_path or Tiku.CONFIG_PATH
    if not conf:
        # 尝试从默认配置文件加载
        try:
            config_parser = configparser.ConfigParser()
            config_parser.read(path, encoding="utf8")
            conf = config_parser['tiku']
        except (KeyError, FileNotFoundError):
            logger.error("未找到题库配置, 已忽略题库功能")
            return DummyTiku(config_path=path)

    try:
        cls_name = conf['provider']
        if not cls_name:
            raise KeyError
    except KeyError:
        logger.error("未找到题库配置, 已忽略题库功能")
        return DummyTiku(config_path=path)

    providers = [name.strip() for name in cls_name.split(',') if name.strip()]
    if not providers:
        logger.error("题库provider配置为空, 已忽略题库功能")
        return DummyTiku(config_path=path)

    invalid_providers = [name for name in providers if name not in PROVIDER_REGISTRY]
    if invalid_providers:
        logger.error(f"题库provider配置无效: {', '.join(invalid_providers)}")
        return DummyTiku(config_path=path)

    if len(providers) == 1:
        provider_cls = PROVIDER_REGISTRY[providers[0]]
        if not isinstance(provider_cls, type) or not issubclass(provider_cls, Tiku):
            logger.error(f"题库provider配置无效: {providers[0]}")
            return DummyTiku(config_path=path)
        new_cls = provider_cls(config_path=path)
        new_cls.config_set(conf)
        return new_cls

    chain_providers = []
    for provider_name in providers:
        provider_cls = PROVIDER_REGISTRY[provider_name]
        if not isinstance(provider_cls, type) or not issubclass(provider_cls, Tiku):
            logger.error(f"题库provider配置无效: {provider_name}")
            return DummyTiku(config_path=path)
        provider = provider_cls(config_path=path)
        provider.config_set(conf)
        chain_providers.append(provider)
    fallback = TikuFallback(chain_providers, config_path=path)
    fallback.config_set(conf)
    return fallback
