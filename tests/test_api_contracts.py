"""合成输入上的离线请求对照；不代表服务器已验证这些协议。"""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from api.base import Chaoxing, StudyResult

FIXTURES = Path(__file__).parent / "fixtures" / "api_contracts"


def load_sample(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf8"))


def response(payload=None, text="", status=200):
    return SimpleNamespace(status_code=status, text=text, json=lambda: deepcopy(payload))


class RecordingSession:
    """发送前深拷贝，而非在调用结束后检查可能已被改写的 dict。"""
    def __init__(self, get_responses, post_responses=()):
        self.get_responses = iter(get_responses)
        self.post_responses = iter(post_responses)
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append(("GET", url, deepcopy(kwargs)))
        return next(self.get_responses)

    def post(self, url, **kwargs):
        self.requests.append(("POST", url, deepcopy(kwargs)))
        return next(self.post_responses)


class SyntheticTiku:
    DISABLE = False
    COVER_RATE = 0.8
    is_manual = False

    def __init__(self, rounds, submit_params=""):
        self.query_all = Mock(side_effect=deepcopy(rounds))
        self.set_work_feedback = Mock()
        self.submit_params = submit_params

    def get_submit_params(self):
        return self.submit_params

    def judgement_select(self, answer):
        return answer == "正确"


class OfflineContractTest(unittest.TestCase):
    def setUp(self):
        self.start_patch("requests.sessions.Session.request", side_effect=AssertionError("禁止真实 HTTP"))
        self.start_patch("api.base.use_cookies", side_effect=AssertionError("禁止读取真实 Cookie"))
        self.start_patch("api.base.logger")
        self.start_patch("api.decode.logger")

    def start_patch(self, target, **kwargs):
        patcher = patch(target, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result


class VideoContractTest(OfflineContractTest):
    def setUp(self):
        super().setUp()
        self.sample = load_sample("video.json")
        self.client = Chaoxing()
        self.client.get_uid = Mock(return_value=self.sample["uid"])
        self.client.get_fid = Mock(return_value=self.sample["fid"])
        self.client.video_log_limiter.limit_rate = Mock()
        self.start_patch("api.base.get_timestamp", return_value=self.sample["timestamp"])

    def test_fixed_signature_vectors(self):
        for position, expected in self.sample["signatures"].items():
            with self.subTest(position=position):
                self.assertEqual(self.client.get_enc("1001", "video-001", "synthetic-object",
                                                     int(position), 120, "9001"), expected)

    def test_study_video_first_subsequent_and_final_requests(self):
        s = self.sample
        session = RecordingSession([response(s["status"])] +
                                   [response({"isPassed": passed}) for passed in (False, False, True)])
        self.start_patch("api.base.SessionManager.get_session", return_value=session)
        clock = [0]
        self.start_patch("api.base.time.time", side_effect=lambda: clock[0])
        self.start_patch("api.base.time.sleep", side_effect=lambda _: clock.__setitem__(0, clock[0] + 75))
        self.start_patch("api.base.random.uniform", return_value=30)
        bars = self.start_patch("api.base.tqdm")
        result = self.client.study_video(s["course"], deepcopy(s["job"]), {})
        self.assertIs(result, StudyResult.SUCCESS)
        expected = [("GET", s["status_request"]["url"], {"headers": s["status_request"]["headers"]})]
        expected.extend(("GET", s["log_url"], {"params": s["common_params"] | step, "headers": s["headers"]})
                        for step in s["log_steps"])
        self.assertEqual(session.requests, expected)
        bars.return_value.close.assert_called_once()
        self.assertEqual(self.client.video_log_limiter.limit_rate.call_count, 3)

    def test_optional_video_fields_are_absent_when_empty(self):
        s = self.sample
        job = deepcopy(s["job"])
        job.update(videoFaceCaptureEnc="", attDuration=0, attDurationEnc="", rt="1")
        session = RecordingSession([response({"isPassed": False})])
        self.assertEqual(self.client.video_progress_log(session, s["course"], job, {},
                                                       "SYNTHETIC_DTOKEN", 120, 45), (False, 200))
        params = s["common_params"] | s["log_steps"][1]
        for field in ("videoFaceCaptureEnc", "attDuration", "attDurationEnc"):
            params.pop(field)
        self.assertEqual(session.requests, [("GET", s["log_url"], {"params": params, "headers": s["headers"]})])

    def test_audio_uses_audio_headers_and_dtype(self):
        s = self.sample
        session = RecordingSession([response(s["status"]), response({"isPassed": True})])
        self.start_patch("api.base.SessionManager.get_session", return_value=session)
        result = self.client.study_video(s["course"], deepcopy(s["job"]), {}, _type="Audio")
        self.assertIs(result, StudyResult.SUCCESS)
        headers = {"Referer": "https://mooc1.chaoxing.com/ananas/modules/audio/index_new.html?v=2025-0725-1842"}
        self.assertEqual(session.requests, [
            ("GET", s["status_request"]["url"], {"headers": headers}),
            ("GET", s["log_url"], {"params": s["common_params"] | s["log_steps"][0] | {"dtype": "Audio"},
                                    "headers": headers}),
        ])


class WorkContractTest(OfflineContractTest):
    def setUp(self):
        super().setUp()
        self.sample = load_sample("work.json")
        self.page = (FIXTURES / "work.html").read_text(encoding="utf8")
        self.start_patch("api.base.time.sleep")
        self.start_patch("api.base.random_answer", return_value=self.sample["random_answer"])

    def run_work(self, rounds, forms, *, save=False, manual=False, redo=False, retries=2, result_info=None, client=None):
        s = self.sample
        tiku = SyntheticTiku(rounds, "1" if save else "")
        tiku.is_manual = manual
        session = RecordingSession([response(text=self.page)] * len(forms),
                                   [response({"status": True, "msg": "synthetic"})] * len(forms))
        client = client or Chaoxing()
        client.tiku = tiku
        client.kwargs = {"work_redo_enabled": redo, "work_max_retries": retries, "query_delay": 0.25}
        check = Mock(return_value=deepcopy(result_info))
        with patch("api.base.SessionManager.get_session", return_value=session), \
                patch.object(client, "_check_work_result", check):
            result = client.study_work(s["course"], s["job"], s["job_info"])
        self.assertIs(result, StudyResult.SUCCESS)  # 不解释为服务端确认任务点完成
        expected = []
        for form in forms:
            expected.extend([
                ("GET", s["fetch_url"], {"params": s["fetch_params"]}),
                ("POST", s["submit_url"], {"data": s["common_form"] | s["forms"][form], "headers": s["headers"]}),
            ])
        self.assertEqual(session.requests, expected)
        self.assertEqual(tiku.query_all.call_count, len(forms))
        for call in tiku.query_all.call_args_list:
            self.assertEqual(call.kwargs, {"query_delay": 0.25})
        self.assertEqual(check.call_count, sum(s["forms"][f]["pyFlag"] == "" for f in forms))
        return client, tiku

    def test_full_coverage_submits_all_question_types(self):
        self.run_work([self.sample["answers"]], ["full_submit"])

    def test_explicit_save_overrides_full_coverage(self):
        self.run_work([self.sample["answers"]], ["full_save"], save=True, redo=True)

    def test_low_coverage_save_omits_random_answers(self):
        answers = self.sample["answers"][:2] + [None] * 3
        self.run_work([answers], ["low_coverage_save"], redo=True)

    def test_exact_coverage_threshold_submits_including_random_answer(self):
        self.run_work([self.sample["answers"][:4] + [None]], ["threshold_submit"])

    def test_manual_mode_bypasses_coverage_threshold(self):
        self.run_work([[None] * 5], ["random_submit"], manual=True)

    def test_redo_limit_and_feedback_preserve_submission_forms(self):
        _, tiku = self.run_work([self.sample["answers"], [None] * 5, [None] * 5],
                                ["full_submit", "random_submit", "random_submit"], redo=True,
                                result_info=self.sample["incorrect_result"])
        self.assertEqual(tiku.set_work_feedback.call_count, 2)
        self.assertEqual(tiku.set_work_feedback.call_args.args, (self.sample["incorrect_result"]["feedback"],))

    def test_disabled_redo_keeps_single_submission(self):
        _, tiku = self.run_work([self.sample["answers"]], ["full_submit"],
                                result_info=self.sample["incorrect_result"])
        tiku.set_work_feedback.assert_not_called()

    def test_redo_state_does_not_leak_into_next_work(self):
        client, _ = self.run_work([self.sample["answers"], [None] * 5], ["full_submit", "random_submit"],
                                  redo=True, retries=1, result_info=self.sample["incorrect_result"])
        self.run_work([self.sample["answers"][:2] + [None] * 3], ["low_coverage_save"], client=client)


if __name__ == "__main__":
    unittest.main()
