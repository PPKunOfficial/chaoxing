"""纯答案规则：校验、切分与归一化。

`cut` 的分隔符顺序是行为契约: 按 `CUT_CHARACTERS` 的固定顺序取首个能在答案中
切出内容的字符, 不能替换为同时匹配全部分隔符的正则。
"""

import re

# 切分优先级: 顺序即优先级, 调整顺序会改变已命中的切分结果。
CUT_CHARACTERS = [
    "\n",
    ",",
    "，",
    "|",
    "\r",
    "\t",
    "#",
    "*",
    "-",
    "_",
    "+",
    "@",
    "~",
    "/",
    "\\",
    ".",
    "&",
    " ",
    "、",
]


def check_single(answer):
    if answer is None:
        return False

    text = str(answer).strip()
    if not text:
        return False

    # 单选答案文本中常见逗号（中英文）是句内标点，不应据此判定为多选。
    # 仅在出现明显“多段答案”分隔符时，才判定为非单选。
    strong_delimiters = ["\n", "|", "#", "\t", "\r", "、"]
    for sep in strong_delimiters:
        parts = [p.strip() for p in text.split(sep) if p.strip()]
        if len(parts) > 1:
            return False

    return True


def check_multiple(answer):
    _t = cut(answer)
    if _t is not None and len(_t) > 0:
        return True
    return False


def check_judgement(answer, true_list, false_list):
    val = str(answer).strip().lower()
    if val in ['true', 't', '1', '对', '正确', '√', '是', 'yes', 'y'] or val in [x.lower() for x in true_list]:
        return 1
    elif val in ['false', 'f', '0', '错', '错误', '×', '否', 'no', 'n', '不对', '不正确'] or val in [x.lower() for x in
                                                                                                     false_list]:
        return 0
    else:
        return -1


def check_completion(answer):
    return len(answer) > 0


def check_answer(answer, type, tiku):  # 只会写小杯代码，这里用个tiku感觉怪怪的，但先这么写着
    # 如果是手动模式或多题库回退包装器，直接信任
    # （手动模式豁免常规校验；回退包装器因其子题库在各自环节均已单独校验过，此处无需二次校验，以防二次过滤误杀）
    if getattr(tiku, 'is_manual', False) or getattr(tiku, 'skip_answer_validation', False):
        return True

    if type == 'single':
        if check_single(answer) and check_judgement(answer, tiku.true_list, tiku.false_list) == -1:
            return True
    elif type == 'multiple':
        if check_multiple(answer) and check_judgement(answer, tiku.true_list, tiku.false_list) == -1:
            return True
    elif type == 'completion':
        if check_completion(answer):
            return True
    elif type == 'judgement':
        if check_judgement(answer, tiku.true_list, tiku.false_list) != -1:
            return True
    else:  # 未知类型不匹配
        return True
    return False


def cut(answer):
    if answer is None:
        return None

    answer = str(answer)
    for char in CUT_CHARACTERS:
        if char not in answer:
            continue
        res = [opt.strip() for opt in answer.split(char) if opt.strip()]
        if res:
            return res
    stripped = answer.strip()
    return [stripped] if stripped else None


# 作答详情判分: 归一化与逐题比对
JUDGE_TRUE_SET = {'TRUE', 'T', '1', '对', '正确', '√', '是', 'YES', 'Y'}
JUDGE_FALSE_SET = {'FALSE', 'F', '0', '错', '错误', '×', 'X', '否', 'NO', 'N', '不对', '不正确'}


def normalize_answer_text(ans) -> str:
    """作答详情答案归一化: 消除 对/错与true/false、全半角标点等格式差异.

    归一化是确定性的, 两侧同格式必然相等; 跨格式差异(如字母 vs 选项全文)
    交由调用方的满分分数兜底处理.
    """
    s = re.sub(r'\s+', '', str(ans or '')).upper()
    if s in JUDGE_TRUE_SET:
        return 'TRUE'
    if s in JUDGE_FALSE_SET:
        return 'FALSE'
    if re.fullmatch(r'[A-Z0-9]+', s):
        return s
    s = re.sub(r'^[A-Z][.、:：)?）]', '', s)
    s = re.sub(r'[，。、！？；：,.!?;:()（）\[\]【】"“”‘’\-_/\\|]', '', s)
    return s


def grade_work_detail(detail: list[dict]) -> tuple[bool, list[str], int]:
    """逐题比对上轮作答详情, 生成重做所需的错误反馈.

    Args:
        detail: api.decode.parse_work_record_detail 的返回值

    Returns:
        (是否全部正确, 错误反馈列表, 答案字段未能解析的题数)
    """
    feedback = []
    all_correct = True
    unknown = 0
    for q in detail:
        if not q.get("parse_ok", True):
            unknown += 1
            all_correct = False
            continue
        my_ans = (q.get("my_answer") or "").strip()
        correct_ans = (q.get("correct_answer") or "").strip()
        if normalize_answer_text(my_ans) != normalize_answer_text(correct_ans):
            all_correct = False
            feedback.append(
                f"- 题目：{q.get('title', '')}\n"
                f"  题型：{q.get('type_label', '')}\n"
                f"  你的上次答案：{my_ans or '(空)'}\n"
                f"  正确答案：{correct_ans or '(空)'}"
            )
    return all_correct, feedback, unknown
