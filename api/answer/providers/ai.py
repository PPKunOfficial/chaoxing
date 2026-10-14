# -*- coding: utf-8 -*-
"""大模型题库 provider：OpenAI 兼容接口作答，支持章节检测错误反馈。"""
import json
import re
import threading
import time
from typing import Optional

import httpx
from openai import OpenAI

from api.answer.core import Tiku
from api.logger import logger


class AI(Tiku):
    # AI大模型答题实现
    def __init__(self, config_path: Optional[str] = None) -> None:
        """初始化AI大模型答题实现."""
        super().__init__(config_path)
        self.name = 'AI大模型答题'
        self.last_request_time = None
        self._lock = threading.Lock()
        self.work_feedback = None  # 章节检测错误反馈（重做时参考）

    def set_work_feedback(self, feedback) -> None:
        """
        设置章节检测上一轮的错误反馈，供重新作答时参考。

        Args:
            feedback: str 或 list[str]，描述答错的题目与正确答案
        """
        self.work_feedback = feedback

    def _build_work_feedback_text(self) -> str:
        """将 work_feedback 转为提示词文本."""
        fb = self.work_feedback
        if not fb:
            return ""
        if isinstance(fb, str):
            return fb
        lines = [
            "你上一次作答的章节检测中有以下题目回答错误，"
            "请根据题目与正确答案仔细思考错因，纠正你的判断，本次作答务必保证每道题都正确："
        ]
        for item in fb:
            lines.append(str(item))
        return "\n".join(lines)

    def _is_deepseek_v4(self) -> bool:
        return (
                'api.deepseek.com' in (self.endpoint or '').lower()
                and (self.model or '').lower().startswith('deepseek-v4')
        )

    def _completion_kwargs(self, **kwargs):
        if self._is_deepseek_v4():
            # DeepSeek V4 defaults to thinking mode, which can leave message.content empty.
            kwargs['extra_body'] = {'thinking': {'type': 'disabled'}}
        return kwargs

    def _wait_for_interval(self):
        if self.last_request_time:
            interval_time = time.time() - self.last_request_time
            if interval_time < self.min_interval_seconds:
                sleep_time = self.min_interval_seconds - interval_time
                logger.debug(f"API请求间隔过短, 等待 {sleep_time} 秒")
                time.sleep(sleep_time)

    def _query(self, q_info: dict):
        with self._lock:
            return self._query_locked(q_info)

    def _query_locked(self, q_info: dict):
        def remove_md_json_wrapper(md_str):
            # 使用正则表达式匹配Markdown代码块并提取内容
            pattern = r'^\s*```(?:json)?\s*(.*?)\s*```\s*$'
            match = re.search(pattern, md_str, re.DOTALL)
            return match.group(1).strip() if match else md_str.strip()

        if self.http_proxy:
            proxy = self.http_proxy
            httpx_client = httpx.Client(proxy=proxy)
            client = OpenAI(http_client=httpx_client, base_url=self.endpoint, api_key=self.key)
        else:
            client = OpenAI(base_url=self.endpoint, api_key=self.key)
        # 去除选项字母，防止大模型直接输出字母而非内容
        options_list = q_info['options'].split('\n')
        cleaned_options = [re.sub(r"^[A-Z]\s*", "", option) for option in options_list]
        options = "\n".join(cleaned_options)

        # 上一轮章节检测的错误反馈（若有）
        feedback_text = self._build_work_feedback_text()

        def _make_messages(system_content: str, user_content: str) -> list:
            """构造带反馈上下文的消息列表."""
            messages = [
                {
                    "role": "system",
                    "content": system_content
                },
            ]
            if feedback_text:
                messages.append(
                    {
                        "role": "system",
                        "content": feedback_text
                    }
                )
            messages.append(
                {
                    "role": "user",
                    "content": user_content
                }
            )
            return messages

        # 判断题目类型
        self._wait_for_interval()
        self.last_request_time = time.time()
        if q_info['type'] == "single":
            completion = client.chat.completions.create(**self._completion_kwargs(
                model=self.model,
                messages=_make_messages(
                    "本题为单选题，你只能选择一个选项，请根据题目和选项回答问题，以json格式输出正确的选项内容，示例回答：{\"Answer\": [\"答案\"]}。除此之外不要输出任何多余的内容，也不要使用MD语法。如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料",
                    f"题目：{q_info['title']}\n选项：{options}"
                )
            ))
        elif q_info['type'] == 'multiple':
            completion = client.chat.completions.create(**self._completion_kwargs(
                model=self.model,
                messages=_make_messages(
                    "本题为多选题，你必须选择两个或以上选项，请根据题目和选项回答问题，以json格式输出正确的选项内容，示例回答：{\"Answer\": [\"答案1\",\n\"答案2\",\n\"答案3\"]}。除此之外不要输出任何多余的内容，也不要使用MD语法。如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料",
                    f"题目：{q_info['title']}\n选项：{options}"
                )
            ))
        elif q_info['type'] == 'completion':
            completion = client.chat.completions.create(**self._completion_kwargs(
                model=self.model,
                messages=_make_messages(
                    "本题为填空题，你必须根据语境和相关知识填入合适的内容，请根据题目回答问题，以json格式输出正确的答案，示例回答：{\"Answer\": [\"答案\"]}。除此之外不要输出任何多余的内容，也不要使用MD语法。如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料",
                    f"题目：{q_info['title']}"
                )
            ))
        elif q_info['type'] == 'judgement':
            completion = client.chat.completions.create(**self._completion_kwargs(
                model=self.model,
                messages=_make_messages(
                    "本题为判断题，你只能回答正确或者错误，请根据题目回答问题，以json格式输出正确的答案，示例回答：{\"Answer\": [\"正确\"]}。除此之外不要输出任何多余的内容，也不要使用MD语法。如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料",
                    f"题目：{q_info['title']}"
                )
            ))
        else:
            completion = client.chat.completions.create(**self._completion_kwargs(
                model=self.model,
                messages=_make_messages(
                    "本题为简答题，你必须根据语境和相关知识填入合适的内容，请根据题目回答问题，以json格式输出正确的答案，示例回答：{\"Answer\": [\"这是我的答案\"]}。除此之外不要输出任何多余的内容，也不要使用MD语法。如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料",
                    f"题目：{q_info['title']}"
                )
            ))

        try:
            response = json.loads(remove_md_json_wrapper(completion.choices[0].message.content))
            sep = "\n"
            return sep.join(response['Answer']).strip()
        except:
            logger.error("无法解析大模型输出内容")
            return None

    def _init_tiku(self):
        self.endpoint = self._conf['endpoint']
        self.key = self._conf['key']
        self.model = self._conf['model']
        self.http_proxy = self._conf['http_proxy']
        self.min_interval_seconds = int(self._conf['min_interval_seconds'])

    def check_llm_connection(self) -> bool:
        """
        检查大模型连接是否可用
        发送一个简单的测试请求来验证 API 配置
        """
        with self._lock:
            logger.info(f'正在检查 {self.name} 连接...')
            try:
                # 初始化客户端
                if self.http_proxy:
                    httpx_client = httpx.Client(proxy=self.http_proxy)
                    client = OpenAI(http_client=httpx_client, base_url=self.endpoint, api_key=self.key)
                else:
                    client = OpenAI(base_url=self.endpoint, api_key=self.key)

                # 限流等待
                self._wait_for_interval()
                self.last_request_time = time.time()

                # 发送测试请求
                completion = client.chat.completions.create(**self._completion_kwargs(
                    model=self.model,
                    messages=[
                        {
                            'role': 'user',
                            'content': '你好，请回答：1+1 等于几？只回答数字。'
                        }
                    ],
                    max_tokens=200  # 增大以支持可能返回的 reasoning_content
                ))

                # 统一检查响应
                if completion.choices:
                    msg = completion.choices[0].message
                    if msg.content or getattr(msg, 'reasoning_content', None):
                        logger.info(f'{self.name} 连接检查成功')
                        return True

                logger.error(f'{self.name} 连接检查失败：未收到响应')
                return False

            except Exception as e:
                logger.error(f'{self.name} 连接检查失败：{e}')
                return False
