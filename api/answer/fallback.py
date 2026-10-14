# -*- coding: utf-8 -*-
"""多题库回退：按配置顺序逐个查询仍未命中的题目。"""
from typing import Optional

from api.answer.core import Tiku
from api.answer_check import check_answer
from api.logger import logger


class TikuFallback(Tiku):
    # 多题库回退实现，按 provider 中配置顺序依次查询。
    def __init__(self, providers=None, config_path: Optional[str] = None):
        """初始化多题库回退."""
        super().__init__(config_path)
        self.name = '多题库回退'
        self.providers = providers or []
        self.skip_answer_validation = True

    def _init_tiku(self):
        active = []
        for provider in self.providers:
            try:
                provider.init_tiku()
                if not provider.DISABLE:
                    active.append(provider)
            except Exception as e:
                logger.error(f'初始化题库 {provider.name} 失败: {e}')
        self.providers = active
        if not self.providers:
            logger.error('多题库回退初始化失败: 没有可用题库')
            self.DISABLE = True
        else:
            logger.info(f"多题库回退已启用，查询顺序: {', '.join([p.__class__.__name__ for p in self.providers])}")

    def _query(self, q_info: dict) -> Optional[str]:
        for provider in self.providers:
            try:
                answer = provider._query(q_info)
            except Exception as e:
                provider_id = f'{provider.name}({provider.__class__.__name__})'
                logger.exception(f'{self.name} 查询时 {provider_id} 异常: {e}')
                continue
            if not answer:
                logger.info(f'{provider.name} 未命中，回退到下一个题库')
                continue

            # 若当前题库返回答案但类型不符，则继续回退。
            if check_answer(answer, q_info['type'], provider):
                logger.info(f'{provider.name} 命中答案')
                return answer

            logger.info(f'{provider.name} 返回答案类型不符，回退到下一个题库')
        return None

    def _query_all(self, q_list: list[dict], query_delay: float = 0.0) -> list[Optional[str]]:
        results = [None] * len(q_list)
        pending_indices = list(range(len(q_list)))

        for provider in self.providers:
            if not pending_indices:
                break
            if provider.DISABLE:
                continue

            sub_q_list = [q_list[idx] for idx in pending_indices]
            try:
                sub_results = provider.query_all(sub_q_list, query_delay=query_delay)
            except Exception as e:
                provider_id = f'{provider.name}({provider.__class__.__name__})'
                logger.exception(f'{self.name} 批量查询时 {provider_id} 异常: {e}')
                continue

            if not isinstance(sub_results, list):
                logger.error(f"{provider.name} 批量查询返回数据格式异常（非列表），跳过该题库")
                continue

            if len(sub_results) != len(pending_indices):
                logger.error(
                    f"{provider.name} 批量查询返回结果长度（{len(sub_results)}）与请求题目数（{len(pending_indices)}）不匹配，跳过该题库以防答案错位")
                continue

            next_pending_indices = []
            for orig_idx, ans in zip(pending_indices, sub_results):
                if ans:
                    logger.info(f'{provider.name} 命中答案: {q_list[orig_idx]["title"]} -> {ans}')
                    results[orig_idx] = ans
                else:
                    logger.info(f'{provider.name} 未命中或返回答案无效，将回退')
                    next_pending_indices.append(orig_idx)
            pending_indices = next_pending_indices

        return results

    def set_work_feedback(self, feedback) -> None:
        """将章节检测错误反馈转发给支持反馈的子题库（如 AI 大模型）."""
        for provider in self.providers:
            if hasattr(provider, 'set_work_feedback'):
                try:
                    provider.set_work_feedback(feedback)
                except Exception as e:
                    logger.warning(f"向子题库 {provider.name} 设置错误反馈失败: {e}")

    def check_llm_connection(self) -> bool:
        for provider in self.providers:
            if not provider.check_llm_connection():
                logger.error(f'{provider.name} 连接检查失败')
                return False
        return True
