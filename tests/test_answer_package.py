# -*- coding: utf-8 -*-
"""题库拆包后的注册表、构造入口与手动模式日志协调回归。

provider 名称与顺序、未知 provider 的整链禁用、手动锁与日志缓冲的联动
都是行为契约，见 `.agents/api重构施工方案.md` 第五节。
"""
import unittest
from unittest.mock import patch

from api.answer.core import Tiku
from api.answer.fallback import TikuFallback
from api.answer.providers.manual import TikuManual
from api.answer.registry import DummyTiku, PROVIDER_REGISTRY, get_tiku_from_config
from api.logger import log_buffer, tqdm_sink
from api.interaction import manual_input_lock

CONFIG_PATH = "config_template.ini"


class ProviderRegistryTest(unittest.TestCase):
    def test_registry_names_and_order_are_stable(self):
        """配置里的 provider 名称与顺序是兼容契约, 拆包不得改动。"""
        self.assertEqual(
            list(PROVIDER_REGISTRY),
            ["TikuYanxi", "TikuGo", "TikuLike", "TikuAdapter", "AI", "SiliconFlow", "TikuManual"],
        )

    def test_registry_values_are_tiku_subclasses(self):
        for name, provider_cls in PROVIDER_REGISTRY.items():
            with self.subTest(provider=name):
                self.assertTrue(issubclass(provider_cls, Tiku))

    def test_unknown_provider_disables_whole_chain(self):
        """未知 provider 目前导致整链禁用, 不改成静默跳过。"""
        tiku = get_tiku_from_config({"provider": "AI,Nope"}, config_path=CONFIG_PATH)
        self.assertIsInstance(tiku, DummyTiku)
        self.assertTrue(tiku.DISABLE)

    def test_chain_order_follows_config(self):
        tiku = get_tiku_from_config({"provider": "AI, SiliconFlow ,TikuManual"}, config_path=CONFIG_PATH)
        self.assertIsInstance(tiku, TikuFallback)
        self.assertEqual([type(provider).__name__ for provider in tiku.providers],
                         ["AI", "SiliconFlow", "TikuManual"])

    def test_single_provider_returns_the_provider_itself(self):
        tiku = get_tiku_from_config({"provider": "TikuManual"}, config_path=CONFIG_PATH)
        self.assertIsInstance(tiku, TikuManual)

    def test_blank_provider_disables_chain(self):
        for conf in ({"provider": " , "}, {"provider": ""}):
            with self.subTest(conf=conf):
                tiku = get_tiku_from_config(dict(conf), config_path=CONFIG_PATH)
                self.assertIsInstance(tiku, DummyTiku)
                self.assertTrue(tiku.DISABLE)

    def test_missing_config_file_disables_chain(self):
        """既无显式配置又读不到配置文件时整链禁用。"""
        tiku = get_tiku_from_config(None, config_path="no-such-config.ini")
        self.assertIsInstance(tiku, DummyTiku)
        self.assertTrue(tiku.DISABLE)

    def test_config_file_supplies_provider_when_conf_missing(self):
        """未传 conf 时仍从配置文件读取 provider。"""
        from api.answer.providers.traditional import TikuYanxi
        tiku = get_tiku_from_config(None, config_path=CONFIG_PATH)
        self.assertIsInstance(tiku, TikuYanxi)


class TikuInstanceStateTest(unittest.TestCase):
    def test_manual_provider_marks_itself_manual(self):
        manual = TikuManual()
        self.assertTrue(manual.is_manual)
        self.assertTrue(manual.skip_answer_validation)
        self.assertTrue(manual._is_manual_mode)

    def test_runtime_state_is_not_shared_between_instances(self):
        """提交/停用/覆盖率是每实例运行状态, 不再是类属性共享。"""
        first, second = TikuManual(), TikuManual()
        first.DISABLE = True
        first.SUBMIT = True
        first.COVER_RATE = 0.5
        self.assertFalse(second.DISABLE)
        self.assertFalse(second.SUBMIT)
        self.assertEqual(second.COVER_RATE, Tiku.DEFAULT_COVER_RATE)

    def test_forwarding_properties_are_gone(self):
        """name/api/token 只做转发的属性已删除, 改为普通实例属性。"""
        tiku = TikuManual()
        self.assertFalse(hasattr(type(tiku), "name"))
        tiku.name = "自定义"
        self.assertEqual(tiku.name, "自定义")


class ManualModeLogCoordinationTest(unittest.TestCase):
    def test_logs_are_buffered_while_manual_lock_is_held(self):
        """手动输入期间日志进缓冲, 解锁后统一输出。"""
        self.addCleanup(log_buffer.clear)
        with patch("api.logger.tqdm.write") as write:
            with manual_input_lock:
                log_buffer.clear()
                tqdm_sink("held-line")
                self.assertIn("held-line", log_buffer)
                write.assert_not_called()

            tqdm_sink("after-line")
            self.assertNotIn("held-line", log_buffer)


if __name__ == "__main__":
    unittest.main()
