# -*- coding: utf-8 -*-
"""题库查询核心：实例状态、查询管道与批量查询模板。"""
import configparser
import os
import random
import time
from abc import ABC, abstractmethod
from typing import Optional

from api.answer_check import check_answer
from api.logger import logger


class Tiku(ABC):
    CONFIG_PATH = os.path.join(os.getcwd(), "config.ini")

    # 配置默认值: 可被配置文件覆盖, 但不随运行改写
    DEFAULT_COVER_RATE = 0.8

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        初始化题库基类。

        Args:
            config_path: 配置文件路径，若为 None 则使用默认的 CONFIG_PATH。
        """
        self.name = None
        self.api = None
        self.token = None
        self._conf = None
        self._config_path = config_path or self.CONFIG_PATH
        self.true_list = []
        self.false_list = []
        # 运行状态: 每个实例独立, 避免一个题库改写另一个题库的提交与覆盖率
        self.DISABLE = False  # 停用标志
        self.SUBMIT = False  # 提交标志
        self.COVER_RATE = self.DEFAULT_COVER_RATE  # 覆盖率

    def init_tiku(self):
        # 仅用于题库初始化, 应该在题库载入后作初始化调用, 随后才可以使用题库
        # 尝试根据配置文件设置提交模式
        if not self._conf:
            self.config_set(self._get_conf())
        if not self.DISABLE:
            # 设置提交模式
            self.SUBMIT = True if self._conf['submit'] == 'true' else False
            self.COVER_RATE = float(self._conf['cover_rate'])
            self.true_list = self._conf['true_list'].split(',')
            self.false_list = self._conf['false_list'].split(',')
            # 调用自定义题库初始化
            self._init_tiku()

    def _init_tiku(self):
        # 仅用于题库初始化, 例如配置token, 交由自定义题库完成
        pass

    def config_set(self, config):
        self._conf = config

    def _get_conf(self):
        """
        从默认配置文件查询配置, 如果未能查到, 停用题库
        """
        try:
            config = configparser.ConfigParser()
            config.read(self._config_path, encoding="utf8")
            return config['tiku']
        except (KeyError, FileNotFoundError):
            logger.info("未找到tiku配置, 已忽略题库功能")
            self.DISABLE = True
            return None

    @property
    def _is_manual_mode(self) -> bool:
        return (
                getattr(self, 'is_manual', False) or
                self.__class__.__name__ == 'TikuManual' or
                (self.__class__.__name__ == 'TikuFallback' and any(
                    getattr(p, 'is_manual', False) or p.__class__.__name__ == 'TikuManual' for p in
                    getattr(self, 'providers', [])))
        )

    def query(self, q_info: dict) -> Optional[str]:
        if self.DISABLE:
            return None

        # 预处理, 去除【单选题】这样与标题无关的字段
        if not self._is_manual_mode:
            logger.debug(f"原始标题：{q_info['title']}")
        q_info['title'] = sub(r'^\d+', '', q_info['title'])
        q_info['title'] = sub(r'（\d+\.\d+分）$', '', q_info['title'])
        if not self._is_manual_mode:
            logger.debug(f"处理后标题：{q_info['title']}")

        # 先过缓存（若存在章节检测错误反馈，说明处于重做模式，跳过缓存让大模型参考反馈重新作答）
        if not getattr(self, 'work_feedback', None):
            cache_dao = CacheDAO()
            answer = cache_dao.get_cache(q_info['title'])
            if answer:
                logger.info(f"从缓存中获取答案：{q_info['title']} -> {answer}")
                return answer.strip()
            else:
                answer = self._query(q_info)
        else:
            answer = self._query(q_info)
            if answer:
                answer = answer.strip()
                logger.info(f"从{self.name}获取答案：{q_info['title']} -> {answer}")
                if check_answer(answer, q_info['type'], self):
                    cache_dao.add_cache(q_info['title'], answer)
                    return answer
                else:
                    logger.info(f"从{self.name}获取到的答案类型与题目类型不符，已舍弃")
                    return None

            logger.error(f"从{self.name}获取答案失败：{q_info['title']}")
        return None

    def query_all(self, q_list: list[dict], query_delay: float = 0.0) -> list[Optional[str]]:
        if self.DISABLE:
            return [None] * len(q_list)

        results = [None] * len(q_list)
        pending_indices = []

        cache_dao = CacheDAO()
        skip_cache = bool(getattr(self, 'work_feedback', None))
        for idx, q in enumerate(q_list):
            if not self._is_manual_mode:
                logger.debug(f"原始标题：{q['title']}")
            q['title'] = sub(r'^\d+', '', q['title'])
            q['title'] = sub(r'（\d+\.\d+分）$', '', q['title'])
            if not self._is_manual_mode:
                logger.debug(f"处理后标题：{q['title']}")

            if skip_cache:
                # 重做模式：不走缓存，让大模型参考错误反馈重新作答
                pending_indices.append(idx)
                continue

            answer = cache_dao.get_cache(q['title'])
            if answer:
                logger.info(f"从缓存中获取答案：{q['title']} -> {answer}")
                results[idx] = answer.strip()
            else:
                pending_indices.append(idx)

        if not pending_indices:
            return results

        sub_q_list = [q_list[idx] for idx in pending_indices]
        sub_results = self._query_all(sub_q_list, query_delay=query_delay)

        if not isinstance(sub_results, list):
            logger.error(f"{self.name} _query_all 返回结果格式异常，期望列表")
            sub_results = [None] * len(pending_indices)
        elif len(sub_results) != len(pending_indices):
            logger.error(
                f"{self.name} _query_all 返回结果长度不匹配，期望 {len(pending_indices)}，实际 {len(sub_results)}")
            # 补齐或截断 sub_results 防止错位
            sub_results = list(sub_results) + [None] * (len(pending_indices) - len(sub_results))
            sub_results = sub_results[:len(pending_indices)]

        for idx, ans in zip(pending_indices, sub_results):
            q_info = q_list[idx]
            if ans:
                ans = ans.strip()
                logger.info(f"从{self.name}获取答案：{q_info['title']} -> {ans}")
                if check_answer(ans, q_info['type'], self):
                    cache_dao.add_cache(q_info['title'], ans)
                    results[idx] = ans
                else:
                    logger.info(f"从{self.name}获取到的答案类型与题目类型不符，已舍弃")
            else:
                logger.error(f"从{self.name}获取答案失败：{q_info['title']}")

        return results

    @abstractmethod
    def _query(self, q_info: dict) -> Optional[str]:
        """
        查询接口, 交由自定义题库实现
        """
        pass


    def set_work_feedback(self, feedback) -> None:
        """
        设置上一轮章节检测的错误反馈，供支持反馈的大模型题库在重新作答时参考。

        Args:
            feedback: 错误反馈，可以是 str 或 list[str]（描述哪些题目答错、正确答案是什么）
        """
        pass

    def _query_all(self, q_list: list[dict], query_delay: float = 0.0) -> list[Optional[str]]:
        """
        批量查询的实现接口，默认循环调用单个查询 _query。
        子类若有批量查询或交互需求（如手动模式），可重写此方法。
        """
        results = []
        for q in q_list:
            if query_delay > 0:
                time.sleep(query_delay)
            try:
                results.append(self._query(q))
            except Exception as e:
                logger.error(f"{self.name} 查询单个题目发生异常: {e}")
                results.append(None)
        return results

    def judgement_select(self, answer: str) -> bool:
        """
        这是一个专用的方法, 要求配置维护两个选项列表, 一份用于正确选项, 一份用于错误选项, 以应对题库对判断题答案响应的各种可能的情况
        它的作用是将获取到的答案answer与可能的选项列对比并返回对应的布尔值
        """
        if self.DISABLE:
            return False
        # 对响应的答案作处理
        answer = answer.strip().lower()

        # 内置的高频通用判断词规整
        if answer in ['true', 't', '1', '对', '正确', '√', '是', 'yes', 'y']:
            return True
        if answer in ['false', 'f', '0', '错', '错误', '×', '否', 'no', 'n', '不对', '不正确']:
            return False

        # 兼容自定义配置列表
        if answer in [x.lower() for x in self.true_list] or answer in self.true_list:
            return True
        elif answer in [x.lower() for x in self.false_list] or answer in self.false_list:
            return False
        else:
            # 无法判断, 随机选择
            logger.error(
                f'无法判断答案 -> {answer} 对应的是正确还是错误, 请自行判断并加入配置文件重启脚本, 本次将会随机选择选项')
            return random.choice([True, False])

    def get_submit_params(self):
        """
        这是一个专用方法, 用于根据当前设置的提交模式, 响应对应的答题提交API中的pyFlag值
        """
        # 留空直接提交, 1保存但不提交
        if self.SUBMIT:
            return ""
        else:
            return "1"

    def check_llm_connection(self) -> bool:
        """
        检查大模型连接是否可用
        默认返回 True（非大模型题库不需要检查）
        """
        return True
