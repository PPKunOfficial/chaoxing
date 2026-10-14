"""纯答案规则：校验、切分与归一化。

`cut` 的分隔符顺序是行为契约: 按 `CUT_CHARACTERS` 的固定顺序取首个能在答案中
切出内容的字符, 不能替换为同时匹配全部分隔符的正则。
"""

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
