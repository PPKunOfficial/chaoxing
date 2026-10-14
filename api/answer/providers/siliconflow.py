# -*- coding: utf-8 -*-
"""硅基流动大模型题库 provider，按题目类型构造提示词并解析 JSON 答案。"""
import json
import re
import threading
import time
from typing import Optional

import requests

from api.answer.core import Tiku
from api.logger import logger


class SiliconFlow(Tiku):

    def __init__(self, config_path: Optional[str] = None):
        """初始化硅基流动大模型题库."""
        super().__init__(config_path)
        self.name = '硅基流动大模型'
        self.last_request_time = None
        self._lock = threading.Lock()

    def _wait_for_interval(self):
        if self.last_request_time:
            interval = time.time() - self.last_request_time
            if interval < self.min_interval:
                sleep_time = self.min_interval - interval
                logger.debug(f"API请求间隔过短, 等待 {sleep_time} 秒")
                time.sleep(sleep_time)

    def _query(self, q_info: dict):
        with self._lock:
            return self._query_locked(q_info)

    def _query_locked(self, q_info: dict):
        def remove_md_json_wrapper(md_str):
            # 解析可能存在的JSON包装
            pattern = r'^\s*```(?:json)?\s*(.*?)\s*```\s*$'
            match = re.search(pattern, md_str, re.DOTALL)
            return match.group(1).strip() if match else md_str.strip()

        # 构造请求头
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 构造系统提示词
        system_prompt = ""
        if q_info['type'] == "single":
            system_prompt = "本题为单选题，请根据题目和选项选择唯一正确答案，输出的是选项的具体内容，而不是内容前的ABCD，并以JSON格式输出：示例回答：{\"Answer\": [\"正确选项内容\"]}。除此之外不要输出任何多余的内容，也不要使用MD语法。如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
        elif q_info['type'] == 'multiple':
            system_prompt = "本题为多选题，请选择所有正确选项，输出的是选项的具体内容，而不是内容前的ABCD，以JSON格式输出：示例回答：{\"Answer\": [\"选项1\",\"选项2\"]}。除此之外不要输出任何多余的内容，也不要使用MD语法。如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
        elif q_info['type'] == 'completion':
            system_prompt = "本题为填空题，请直接给出填空内容，以JSON格式输出：示例回答：{\"Answer\": [\"答案文本\"]}。除此之外不要输出任何多余的内容，也不要使用MD语法。如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
        elif q_info['type'] == 'judgement':
            system_prompt = "本题为判断题，请回答'正确'或'错误'，以JSON格式输出：示例回答：{\"Answer\": [\"正确\"]}。除此之外不要输出任何多余的内容，也不要使用MD语法。如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"

        # 构造请求体
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": f"题目：{q_info['title']}\n选项：{q_info['options']}"
                }
            ],
            "stream": False,

            "max_tokens": 4096,

            "temperature": 0.7,
            "top_p": 0.7,
            "response_format": {"type": "text"}
        }

        self._wait_for_interval()

        try:
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            self.last_request_time = time.time()

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                parsed = json.loads(remove_md_json_wrapper(content))
                return "\n".join(parsed['Answer']).strip()
            else:
                logger.error(f"API请求失败：{response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"硅基流动API异常：{e}")
            return None

    def _init_tiku(self):
        # 从配置文件读取参数
        self.api_endpoint = self._conf.get('siliconflow_endpoint', 'https://api.siliconflow.cn/v1/chat/completions')
        self.api_key = self._conf['siliconflow_key']

        self.model_name = self._conf.get('siliconflow_model', 'deepseek-ai/DeepSeek-V3')

        self.min_interval = int(self._conf.get('min_interval_seconds', 3))

    def check_llm_connection(self) -> bool:
        """
        检查硅基流动大模型连接是否可用
        发送一个简单的测试请求来验证 API 配置
        """
        with self._lock:
            logger.info(f'正在检查 {self.name} 连接...')
            try:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    'model': self.model_name,
                    'messages': [
                        {
                            'role': 'user',
                            'content': '你好，请回答：1+1 等于几？只回答数字。'
                        }
                    ],
                    'stream': False,
                    'max_tokens': 10,
                    'temperature': 0.7,
                    'top_p': 0.7,
                    'response_format': {'type': 'text'}
                }

                # 在测试 API 连接时同样执行节流校验
                self._wait_for_interval()

                response = requests.post(
                    self.api_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                self.last_request_time = time.time()

                if response.status_code == 200:
                    result = response.json()
                    if result.get('choices') and result['choices'][0]['message']['content']:
                        logger.info(f'{self.name} 连接检查成功')
                        return True
                    else:
                        logger.error(f'{self.name} 连接检查失败：未收到有效响应')
                        return False
                else:
                    logger.error(f'{self.name} 连接检查失败：{response.status_code} {response.text}')
                    return False

            except Exception as e:
                logger.error(f'{self.name} 连接检查失败：{e}')
                return False
