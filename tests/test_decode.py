# -*- coding: utf-8 -*-
"""解析层界面向量测试：课程、章节、任务卡片、题目表单与作答记录。

样本为脱敏构造的页面片段，覆盖未开放、已完成、缺字段、直播识别与 parse_ok
等边界；不包含真实账号、Cookie 或线上响应。
"""
import json
import unittest

from api.decode import (
    decode_course_card,
    decode_course_folder,
    decode_course_list,
    decode_course_point,
    decode_questions_info,
    parse_work_record_detail,
    parse_work_record_list,
    parse_work_score,
)

COURSE_LIST = """
<div class="course" id="c1" info="i1" roleid="2">
  <input class="clazzId" value="1001"><input class="courseId" value="2001">
  <a href="https://mooc1.chaoxing.com/visit/interaction?cpi=12345&openc=1">入口</a>
  <span class="course-name" title="课程甲"></span>
  <p class="margint10" title="描述甲"></p>
  <p class="color3" title="老师甲"></p>
</div>
<div class="course" id="c2" info="i2" roleid="2">
  <div class="not-open-tip">未开放</div>
  <input class="clazzId" value="1002"><input class="courseId" value="2002">
  <a href="?cpi=999&x=1"></a><span class="course-name" title="未开放课"></span><p class="color3" title="老师乙"></p>
</div>
<div class="course" id="c3" info="i3" roleid="2">
  <input class="clazzId" value="1003"><input class="courseId" value="2003">
  <a href="?cpi=777&openc=1"></a><span class="course-name" title="课程丙"></span>
  <p class="margint10" title="描述丙"></p><p class="color3" title="老师丙"></p>
</div>
<div class="course" id="c4" info="i4" roleid="2">
  <a class="not-open-tip">未开放</a>
  <input class="clazzId" value="1004"><input class="courseId" value="2004">
  <a href="?cpi=1&"></a><span class="course-name" title="未开放丁"></span><p class="color3" title="t"></p>
</div>
"""

POINTS = """
<div class="chapter_unit"><ul>
  <li><div id="cur1" class="chapter_item"><a class="clicktitle">\n第一章 </a>
      <input class="knowledgeJobCount" value="3"><span class="bntHoverTips">已完成</span></div></li>
  <li><div id="cur2" class="chapter_item"><a class="clicktitle">第二章</a>
      <span class="bntHoverTips">解锁 </span></div></li>
  <li><div id="cur3" class="chapter_item"><a class="clicktitle">第三章</a></div></li>
  <li><div class="chapter_item"><a class="clicktitle">无id</a></div></li>
</ul></div>
"""

CARDS = {
    "defaults": {"ktoken": "KT", "mtEnc": "MT", "reportTimeInterval": 30, "defenc": "DE",
                 "cardid": "CD", "cpi": "12345", "qnenc": "QN", "knowledgeid": "KN"},
    "attachments": [
        {"type": "live", "jobid": "live-1", "job": {},
         "property": {"title": "直播一", "liveId": "L1", "streamName": "S1"},
         "otherInfo": "nodeId_1-abc&extra=1", "mid": "m1", "objectId": "o1", "aid": "a1"},
        {"type": "video", "jobid": "v1", "job": {},
         "property": {"name": "视频一", "rt": "1.5"},
         "otherInfo": "nodeId_2&extra=2", "mid": "m2", "objectId": "o2", "aid": "a2",
         "playTime": 10, "attDuration": 100, "attDurationEnc": "e", "videoFaceCaptureEnc": "f"},
        {"type": "document", "jobid": "d1", "job": {},
         "property": {"objectid": "obj1"},
         "otherInfo": "nodeId_3&", "jtoken": "jt", "mid": "m3", "enc": "en", "aid": "a3"},
        {"type": "workid", "jobid": "work-9", "job": {}, "property": {}, "otherInfo": "nodeId_4&",
         "mid": "m4", "enc": "en4", "aid": "a4"},
        {"type": "read", "jobid": "r1", "property": {"title": "阅读一", "id": "rid", "read": False},
         "jtoken": "jt", "mid": "m5", "otherInfo": "nodeId_5&", "enc": "en5", "aid": "a5"},
        {"type": "read", "jobid": "r2", "property": {"title": "已读", "read": True}, "mid": "m6"},
        {"type": "video", "jobid": "v2", "job": {}, "isPassed": True,
         "property": {"name": "已通过"}, "mid": "m7"},
        {"type": "video", "jobid": "v3", "job": {}, "property": {"name": "无mid"},
         "otherInfo": "nodeId_6&", "aid": "a6"},
        {"type": "weird", "jobid": "w1", "job": {}, "property": {}, "mid": "m8",
         "otherInfo": "nodeId_7&"},
    ],
}


def _card_html(cards=CARDS):
    body = json.dumps(cards, ensure_ascii=False)[1:-1]
    return "<script>mArg={" + body + "};</script>"


QUESTIONS = """
<html><body><form action="/submit">
<input name="workId" value="123"><input name="pyFlag" value=""><input name="answerX" value="ignored">
<input name="cpi" value="12345"><input value="noname">
<div class="singleQuesId" data="101">
  <div class="TiMu" data="0"></div>
  <div class="Zy_TItle"><span class="newZy_TItle">【单选题】</span>第一题？<img src="a.png">尾部</div>
  <ul><li aria-label="B、选项二">B、选项二</li><li aria-label="A、选项一">A、选项一</li></ul>
</div>
<div class="singleQuesId" data="102">
  <div class="TiMu" data="3"></div>
  <div class="Zy_TItle">判断题题干</div>
  <ul><li>正确选择</li><li>错误选择</li></ul>
</div>
<div class="singleQuesId" data="103">
  <div class="TiMu" data="9"></div>
  <div class="Zy_TItle">未知题型</div>
</div>
</form></body></html>
"""


class DecodeCourseListTest(unittest.TestCase):
    def test_skips_not_open_and_keeps_details(self):
        courses = decode_course_list(COURSE_LIST)
        self.assertEqual([c["id"] for c in courses], ["c1", "c3"])
        self.assertEqual(courses[0]["cpi"], "12345")
        self.assertEqual(courses[0]["desc"], "描述甲")
        self.assertEqual(courses[0]["teacher"], "老师甲")

    def test_missing_description_falls_back_to_empty(self):
        self.assertEqual(decode_course_list(COURSE_LIST)[1]["desc"], "描述丙")

    def test_folder_requires_fileid(self):
        html = ('<ul class="file-list"><li fileid="f1"><input class="rename-input" value="R1"></li>'
                '<li><input class="rename-input" value="R2"></li></ul>')
        self.assertEqual(decode_course_folder(html), [{"id": "f1", "rename": "R1"}])


class DecodeCoursePointTest(unittest.TestCase):
    def test_point_states(self):
        result = decode_course_point(POINTS)
        self.assertTrue(result["hasLocked"])
        points = {p["id"]: p for p in result["points"]}
        self.assertEqual(set(points), {"1", "2", "3"})
        self.assertEqual(points["1"]["jobCount"], "3")
        self.assertTrue(points["1"]["has_finished"])
        self.assertEqual(points["2"]["jobCount"], 1)
        self.assertTrue(points["2"]["need_unlock"])
        self.assertFalse(points["3"]["need_unlock"])
        self.assertFalse(points["3"]["has_finished"])

    def test_locked_point_marks_course_locked(self):
        html = ('<div class="chapter_unit"><ul><li><div id="cur5">'
                '<a class="clicktitle">锁章</a><span class="bntHoverTips">解锁</span></div></li></ul></div>')
        result = decode_course_point(html)
        self.assertTrue(result["hasLocked"])
        self.assertTrue(result["points"][0]["need_unlock"])


class DecodeCourseCardTest(unittest.TestCase):
    def test_not_open_chapter(self):
        self.assertEqual(decode_course_card("章节未开放"), ([], {"notOpen": True}))

    def test_missing_marg_returns_empty(self):
        self.assertEqual(decode_course_card("<html>无 mArg</html>"), ([], {}))

    def test_job_info_defaults(self):
        _, job_info = decode_course_card(_card_html())
        self.assertEqual(job_info["ktoken"], "KT")
        self.assertEqual(job_info["reportTimeInterval"], 30)
        self.assertEqual(job_info["knowledgeid"], "KN")

    def test_task_types_and_filters(self):
        jobs, _ = decode_course_card(_card_html())
        types = {job["type"] for job in jobs}
        self.assertEqual(types, {"live", "video", "document", "workid", "read"})
        # isPassed 卡片、缺 mid 的视频与未知类型都不应进入任务列表
        self.assertEqual(len(jobs), 5)
        self.assertNotIn("weird", [job.get("jobid") for job in jobs])

    def test_live_detected_by_property_markers(self):
        cards = {"defaults": {}, "attachments": [
            {"type": "video", "jobid": "v-live", "job": {},
             "property": {"title": "直播伪装", "streamName": "S"},
             "otherInfo": "nodeId_9&", "mid": "m1"},
        ]}
        jobs, _ = decode_course_card(_card_html(cards))
        self.assertEqual(jobs[0]["type"], "live")
        self.assertEqual(jobs[0]["streamName"], "S")

    def test_other_info_is_trimmed_before_equals_sign(self):
        jobs, _ = decode_course_card(_card_html())
        by_jobid = {job["jobid"]: job for job in jobs}
        self.assertEqual(by_jobid["live-1"]["otherinfo"], "nodeId_1-abc")
        self.assertEqual(by_jobid["v1"]["otherinfo"], "nodeId_2")

    def test_video_task_fields(self):
        jobs, _ = decode_course_card(_card_html())
        video = next(job for job in jobs if job["jobid"] == "v1")
        self.assertEqual(video["name"], "视频一")
        self.assertEqual(video["rt"], "1.5")
        self.assertEqual(video["attDuration"], 100)

    def test_read_task_requires_unread_property(self):
        jobs, _ = decode_course_card(_card_html())
        read = next(job for job in jobs if job["type"] == "read")
        self.assertEqual(read["jobid"], "r1")
        self.assertEqual(read["id"], "rid")


class DecodeQuestionsInfoTest(unittest.TestCase):
    def setUp(self):
        self.form = decode_questions_info(QUESTIONS)

    def test_form_data_excludes_answer_fields(self):
        self.assertEqual(self.form["workId"], "123")
        self.assertEqual(self.form["pyFlag"], "")
        self.assertEqual(self.form["cpi"], "12345")
        self.assertNotIn("answerX", self.form)
        self.assertNotIn("questions", QUESTIONS)

    def test_answerwqbid_is_built_from_question_ids(self):
        self.assertEqual(self.form["answerwqbid"], "101,102,103,")

    def test_question_types(self):
        kinds = {q["id"]: q["type"] for q in self.form["questions"]}
        self.assertEqual(kinds, {"101": "single", "102": "judgement", "103": "unknown"})

    def test_title_keeps_inline_image_marker(self):
        title = next(q["title"] for q in self.form["questions"] if q["id"] == "101")
        self.assertIn('<img src="a.png">', title)
        self.assertIn("【单选题】", title)

    def test_options_are_sorted_and_joined(self):
        options = next(q["options"] for q in self.form["questions"] if q["id"] == "101")
        self.assertEqual(options.split("\n"), ["A、选项一", "B、选项二"])

    def test_answer_field_is_blanked(self):
        answer_field = next(q["answerField"] for q in self.form["questions"] if q["id"] == "101")
        self.assertEqual(answer_field, {"answer101": "", "answertype101": "0"})


class ParseWorkRecordTest(unittest.TestCase):
    def test_record_list_pairs_times_and_scores(self):
        html = ('<div class="viewNum">第1次</div><div class="viewScore">80分</div>'
                '<div class="viewNum">第2次</div><div class="viewScore">100分</div>')
        self.assertEqual(parse_work_record_list(html), [(1, 80.0), (2, 100.0)])

    def test_record_list_mismatch_falls_back_to_zero_scores(self):
        html = ('<div class="viewNum">第1次</div><div class="viewNum">第3次</div>'
                '<div class="viewScore">100分</div>')
        self.assertEqual(parse_work_record_list(html), [(1, 0.0), (3, 0.0)])

    def test_record_list_without_records(self):
        self.assertEqual(parse_work_record_list("<html></html>"), [])

    def test_detail_marks_unparsed_answers(self):
        html = ('<div class="TiMu singleQuesId" data="100">'
                '<span>我的答案：</span><div class="fl answerCon">A</div></div>')
        detail = parse_work_record_detail(html)
        self.assertEqual(len(detail), 1)
        self.assertFalse(detail[0]["parse_ok"])
        self.assertEqual(detail[0]["my_answer"], "A")
        self.assertEqual(detail[0]["correct_answer"], "")

    def test_empty_detail_returns_empty_list(self):
        self.assertEqual(parse_work_record_detail(""), [])

    def test_work_score(self):
        self.assertEqual(parse_work_score("本次成绩<i>85.5</i>分"), 85.5)
        self.assertEqual(parse_work_score("<html>无成绩</html>"), 0.0)


if __name__ == "__main__":
    unittest.main()
