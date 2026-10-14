# -*- coding: utf-8 -*-
"""手动输入题库 provider：单题与批量交互、输入校验与日志缓冲解锁。"""
import re
import threading
from typing import Optional

from api.answer.core import Tiku
from api.logger import logger


class TikuManual(Tiku):
    _manual_lock = threading.Lock()
    is_manual = True

    def __init__(self, config_path: Optional[str] = None) -> None:
        """初始化手动题库实例."""
        super().__init__(config_path)
        self.name = '手动输入题库'
        self.default_mode = 'batch'
        self.skip_answer_validation = True

    @staticmethod
    def _extract_option_letters(ans: str) -> list[str]:
        cleaned = re.sub(r'[\s,，;；、]+', '', ans)
        if not cleaned or not re.fullmatch(r'[A-Za-z]+', cleaned):
            return []
        return [c.upper() for c in cleaned]

    def _init_tiku(self):
        self.default_mode = self._conf.get('manual_mode_default', 'batch').strip().lower()
        if self.default_mode not in ['batch', 'single']:
            self.default_mode = 'batch'

        self.separator = self._conf.get('manual_mode_separator', ';')
        if self.separator.lower() in ['\\n', 'newline', '换行']:
            self.separator = '\n'
        elif self.separator.lower() in ['space', '空格']:
            self.separator = ' '
        elif self.separator.lower() in ['tab', '制表符']:
            self.separator = '\t'

    @staticmethod
    def _safe_close_tqdm_bars():
        """安全地清除并关闭所有活动的 tqdm 进度条，防止私有属性变更引发异常."""
        try:
            from tqdm import tqdm
            if hasattr(tqdm, '_instances') and hasattr(tqdm._instances, '__iter__'):
                # 复制一份以防遍历时容器大小发生变化 (WeakSet/list)
                instances = list(tqdm._instances)
                for instance in instances:
                    try:
                        if hasattr(instance, 'leave'):
                            instance.leave = False
                        if hasattr(instance, 'clear'):
                            instance.clear()
                        if hasattr(instance, 'close'):
                            instance.close()
                    except Exception as ie:
                        logger.debug(f"清理单个 tqdm 实例失败: {ie}")
        except Exception as e:
            logger.debug(f"获取/清理 tqdm 实例列表失败: {e}")

    def _query(self, q_info: dict) -> Optional[str]:
        # 强行关闭清除所有当前活动的 tqdm 进度条
        self._safe_close_tqdm_bars()

        with self._manual_lock:
            ans = self._single_query(q_info)
        logger.debug("手动答题结束，冲刷缓存日志")
        return ans

    def _query_all(self, q_list: list[dict], query_delay: float = 0.0) -> list[Optional[str]]:
        # 强行关闭清除所有当前活动的 tqdm 进度条
        self._safe_close_tqdm_bars()

        with self._manual_lock:
            print(f"\n{'=' * 20} 手动输入题库 (共 {len(q_list)} 题) {'=' * 20}")
            if self.default_mode == 'batch':
                ans_list = self._batch_query_flow(q_list)
            else:
                ans_list = [self._single_query(q) for q in q_list]
        logger.debug("手动答题结束，冲刷缓存日志")
        return ans_list

    @staticmethod
    def _get_type_display(type_str: str) -> str:
        type_map = {
            'single': '单选题',
            'multiple': '多选题',
            'completion': '填空题',
            'judgement': '判断题'
        }
        return type_map.get(type_str, '其他类型')

    def _single_query(self, q: dict) -> Optional[str]:
        type_str = self._get_type_display(q['type'])
        if q['type'] in ['single', 'multiple'] and q.get('options'):
            options = q['options']
            parts = []
            if isinstance(options, str):
                parts = [o.strip() for o in options.split('\n') if o.strip()]
                if len(parts) <= 1:
                    from api.answer_check import cut
                    cut_parts = cut(options)
                    if cut_parts:
                        parts = cut_parts
            elif isinstance(options, list):
                parts = [str(o).strip() for o in options if str(o).strip()]

            options_text = "  ".join(parts)
            print(f"\n【{type_str}】 {q['title']} 选项: {options_text}")
        elif q['type'] == 'judgement':
            print(f"\n【{type_str}】 {q['title']} 选项: 正确 / 错误")
        else:
            print(f"\n【{type_str}】 {q['title']}")

        while True:
            ans = input("请输入答案 (直接回车表示跳过/无答案): ").strip()
            if not ans:
                print(f"  [已记录] 题目: {q['title']} ---> 答案: [跳过/随机]")
                return None

            # 即时校验
            ok, err_msg = self._validate_user_input(ans, q)
            if not ok:
                print(f"  \033[31m[输入错误] {err_msg}\033[0m")
                continue

            normalized_ans = self._normalize_user_input(ans, q)
            print(f"  [已记录] 题目: {q['title']} ---> 答案: {normalized_ans}")
            return normalized_ans

    def _validate_user_input(self, ans: str, q: dict) -> tuple[bool, str]:
        """
        验证用户手动输入的答案是否合规.
        """
        if not ans:
            return True, ""

        ans = ans.strip()
        if not ans:
            return True, ""

        q_type = q.get('type')
        if q_type == 'judgement':
            return self._validate_judgement_input(ans)
        elif q_type in ['single', 'multiple']:
            return self._validate_choice_input(ans, q)
        return True, ""

    def _validate_judgement_input(self, ans: str) -> tuple[bool, str]:
        """验证判断题手动输入是否合规."""
        val = ans.lower()
        valid_judgements = [
            'true', 't', '1', '对', '正确', '√', '是', 'yes', 'y',
            'false', 'f', '0', '错', '错误', '×', '否', 'no', 'n', '不对', '不正确'
        ]
        if val not in valid_judgements:
            return False, f"无法识别的判断词 '{ans}'，请输入：对/错、正确/错误、T/F、1/0"
        return True, ""

    def _validate_choice_input(self, ans: str, q: dict) -> tuple[bool, str]:
        """
        验证选择题手动输入是否合规.
        """
        options = q.get('options', '')
        parts = self._parse_options(options)
        valid_keys = self._extract_valid_keys(parts)

        if not valid_keys:
            return True, ""

        letters = self._extract_option_letters(ans)
        if not letters:
            return self._validate_text_match(ans, parts)

        invalid_letters = [letter for letter in letters if letter not in valid_keys]
        if invalid_letters:
            return False, f"输入包含无效的选项字母 {invalid_letters}，当前题目的可用选项为: {', '.join(valid_keys)}"

        if q.get('type') == 'single' and len(letters) > 1:
            return False, "当前是单选题，但输入了多个选项字母！"

        return True, ""

    def _parse_options(self, options) -> list[str]:
        """
        解析选项.
        """
        parts = []
        if isinstance(options, str):
            parts = [o.strip() for o in options.split('\n') if o.strip()]
            if len(parts) <= 1:
                from api.answer_check import cut
                cut_parts = cut(options)
                if cut_parts:
                    parts = cut_parts
        elif isinstance(options, list):
            parts = [str(o).strip() for o in options if str(o).strip()]
        return parts

    def _extract_valid_keys(self, parts: list[str]) -> list[str]:
        """
        提取合法的选项字母.
        """
        valid_keys = []
        for p in parts:
            first_char = p[:1].upper()
            if first_char.isalpha():
                valid_keys.append(first_char)
        return valid_keys

    def _validate_text_match(self, ans: str, parts: list[str]) -> tuple[bool, str]:
        """
        验证用户输入的文本是否和选项文本匹配.
        """
        from api.answer_check import cut
        split_ans = cut(ans)
        if split_ans:
            for item in split_ans:
                matched = False
                for p in parts:
                    p_norm = re.sub(r'^[A-Za-z]\s*[.、:：)?）]?\s*', '', p).strip().lower()
                    if item.strip().lower() in p_norm or p_norm in item.strip().lower():
                        matched = True
                        break
                if not matched:
                    return False, f"输入的文本 '{item}' 在所有选项中均无法匹配，请输入合法的选项文本或字母"
        return True, ""

    def _normalize_user_input(self, ans: str, q: dict) -> Optional[str]:
        """
        规整化用户的手动输入答案.
        """
        if not ans:
            return None

        ans = ans.strip()
        if not ans:
            return None

        q_type = q.get('type')
        if q_type == 'judgement':
            return self._normalize_judgement_input(ans)
        elif q_type in ['single', 'multiple']:
            return self._normalize_choice_input(ans, q)
        return ans

    def _normalize_judgement_input(self, ans: str) -> str:
        """
        规整化判断题的手动输入.
        """
        val = ans.lower()
        if val in ['true', 't', '1', '对', '正确', '√', '是', 'yes', 'y']:
            return "正确"
        elif val in ['false', 'f', '0', '错', '错误', '×', '否', 'no', 'n', '不对', '不正确']:
            return "错误"
        return ans

    def _normalize_choice_input(self, ans: str, q: dict) -> str:
        """
        规整化选择题的手动输入.
        """
        options = q.get('options', '')
        parts = self._parse_options(options)
        valid_keys = self._extract_valid_keys(parts)

        letters = self._extract_option_letters(ans)
        if letters and all(letter in valid_keys for letter in letters):
            unique_ordered_letters = []
            for letter in letters:
                if letter not in unique_ordered_letters:
                    unique_ordered_letters.append(letter)
            return "\n".join(unique_ordered_letters)

        from api.answer_check import cut
        split_ans = cut(ans)
        if split_ans:
            return "\n".join(split_ans)
        return ans

    def _batch_query_flow(self, q_list: list[dict]) -> list[Optional[str]]:
        """
        执行批量手动搜题交互.
        """
        self._print_batch_questions(q_list)

        sep_desc = self.separator
        if self.separator == '\n':
            sep_desc = '换行 (每题一行)'
        elif self.separator == ' ':
            sep_desc = '空格'
        elif self.separator == '\t':
            sep_desc = 'Tab制表符'

        self._print_batch_instructions(sep_desc)

        while True:
            answers = []
            if self.separator == '\n':
                print(f"请直接粘贴或依次输入各题答案（每行一个，共 {len(q_list)} 行）：")
                for i in range(len(q_list)):
                    try:
                        ans = input(f"  第 {i + 1} 题答案: ").strip()
                    except EOFError:
                        ans = ""
                    answers.append(ans)
            else:
                raw_input = input(f"\n请一次性输入所有题目的答案 (使用 '{sep_desc}' 分割): ").strip()
                answers = self._split_batch_answers(raw_input, len(q_list))

            has_error, temp_answers = self._parse_and_validate_batch(q_list, answers)

            if has_error:
                print("\033[31m检测到存在不合规的答案，已拒绝确认，请重新输入！\033[0m")
                continue

            confirm = input("确认使用上述答案？[Y/n]: ").strip().lower()
            if confirm in ['', 'y', 'yes']:
                return temp_answers
            elif confirm == 'switch':
                return [self._single_query(q) for q in q_list]
            else:
                print("已取消，请重新输入，或输入 'switch' 切换为单题输入模式。")

    def _print_batch_questions(self, q_list: list[dict]) -> None:
        """批量打印题目内容及选项."""
        for idx, q in enumerate(q_list):
            type_str = self._get_type_display(q['type'])
            if q['type'] in ['single', 'multiple'] and q.get('options'):
                options = q['options']
                parts = []
                if isinstance(options, str):
                    parts = [o.strip() for o in options.split('\n') if o.strip()]
                    if len(parts) <= 1:
                        from api.answer_check import cut
                        cut_parts = cut(options)
                        if cut_parts:
                            parts = cut_parts
                elif isinstance(options, list):
                    parts = [str(o).strip() for o in options if str(o).strip()]

                options_text = "  ".join(parts)
                print(f"\n[{idx + 1}] 【{type_str}】 {q['title']} 选项: {options_text}")
            elif q['type'] == 'judgement':
                print(f"\n[{idx + 1}] 【{type_str}】 {q['title']} 选项: 正确 / 错误")
            else:
                print(f"\n[{idx + 1}] 【{type_str}】 {q['title']}")

    def _print_batch_instructions(self, sep_desc: str) -> None:
        """打印批量输入的使用引导说明."""
        print("\n" + "=" * 50)
        print("请依次输入每道题的答案。")
        print(f"格式要求：当前配置要求使用【{sep_desc}】分割各题的答案。")
        print("如果是多选题，答案中的多个选项直接连着写即可（例如：AB 或 AC）。")
        print("直接按回车或输入空格跳过的题，对应的答案将为空（会触发随机答题）。")
        if self.separator == '\n':
            print("粘贴多行时，每行会被解析为对应一题的答案。")
        else:
            print(f"示例输入: A{self.separator} B{self.separator} 正确{self.separator} 答案1, 答案2{self.separator} 错")
        print("=" * 50)

    def _split_batch_answers(self, raw_input: str, expected_len: int) -> list[str]:
        """根据配置的分割符将批量的答案进行分拆和补齐."""
        if not raw_input:
            return [''] * expected_len

        if self.separator in [';', '；']:
            raw_input = raw_input.replace('；', ';')
            answers = [ans.strip() for ans in raw_input.split(';')]
        elif self.separator in [',', '，']:
            raw_input = raw_input.replace('，', ',')
            answers = [ans.strip() for ans in raw_input.split(',')]
        else:
            answers = [ans.strip() for ans in raw_input.split(self.separator)]

        if len(answers) < expected_len:
            answers.extend([''] * (expected_len - len(answers)))
        elif len(answers) > expected_len:
            answers = answers[:expected_len]
        return answers

    def _parse_and_validate_batch(self, q_list: list[dict], answers: list[str]) -> tuple[bool, list[Optional[str]]]:
        """批量解析用户输入并进行合法性校验."""
        print("\n--- 解析答案结果 ---")
        has_error = False
        temp_answers = []
        for idx, (q, ans) in enumerate(zip(q_list, answers)):
            ok, err_msg = self._validate_user_input(ans, q)
            if not ok:
                has_error = True
                print(f"第 {idx + 1} 题: {q['title']} ---> \033[31m[错误: {err_msg}]\033[0m")
                temp_answers.append(None)
            else:
                normalized_ans = self._normalize_user_input(ans, q)
                temp_answers.append(normalized_ans)
                print(f"第 {idx + 1} 题: {q['title']} ---> 答案: {normalized_ans if normalized_ans else '[跳过/随机]'}")
        print("-------------------")
        return has_error, temp_answers
