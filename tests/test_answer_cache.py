# -*- coding: utf-8 -*-
"""答案缓存并发一致性回归。

契约见 `.agents/api重构施工方案.md` 第四节「修复契约」：指向同一缓存文件的
所有实例共用一把锁，读-改-写串行化，并发写入不得丢更新；只有"文件不存在 /
内容损坏"才按空缓存继续，其他 IO 失败按"缓存不可用"处理而不覆盖整表。
"""
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from api.answer.cache import CacheDAO


class CacheConcurrencyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "cache.json")

    def test_instances_for_same_file_share_one_lock(self):
        first, second = CacheDAO(self.path), CacheDAO(self.path)
        self.assertIs(first._lock, second._lock)

    def test_distinct_files_do_not_share_lock(self):
        other = os.path.join(self._tmp.name, "other.json")
        self.assertIsNot(CacheDAO(self.path)._lock, CacheDAO(other)._lock)

    def test_concurrent_writes_do_not_lose_updates(self):
        """两个实例并发写入, 全部键都必须保留。"""
        per_thread = 200
        first, second = CacheDAO(self.path), CacheDAO(self.path)

        def writer(dao, tag):
            for index in range(per_thread):
                dao.add_cache(f"{tag}-{index}", "A")

        threads = [
            threading.Thread(target=writer, args=(first, "one")),
            threading.Thread(target=writer, args=(second, "two")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        with open(self.path, encoding="utf8") as fp:
            stored = json.load(fp)
        self.assertEqual(len(stored), per_thread * 2)

    def test_corrupt_file_is_backed_up_and_treated_as_empty(self):
        with open(self.path, "w", encoding="utf8") as fp:
            fp.write("{not json")
        dao = CacheDAO(self.path)

        self.assertIsNone(dao.get_cache("题目"))
        backups = [name for name in os.listdir(self._tmp.name) if ".bak." in name]
        self.assertEqual(len(backups), 1)

    def test_non_object_json_is_treated_as_corrupt_without_raising(self):
        """语法合法但根节点不是对象(如 [1])时不得抛 AttributeError/TypeError。"""
        for payload in ("[1]", '"text"', "123", "null"):
            with self.subTest(payload=payload):
                with open(self.path, "w", encoding="utf8") as fp:
                    fp.write(payload)
                dao = CacheDAO(self.path)
                self.assertIsNone(dao.get_cache("题目"))
                self.assertTrue([n for n in os.listdir(self._tmp.name) if ".bak." in n])
                dao.add_cache("题目", "A")
                with open(self.path, encoding="utf8") as fp:
                    self.assertEqual(json.load(fp), {"题目": "A"})

    def test_persistent_read_failure_skips_write_without_clobbering(self):
        """持续读取失败时不得把整表覆盖成只剩新键。"""
        dao = CacheDAO(self.path)
        dao.add_cache("旧题", "A")
        with open(self.path, encoding="utf8") as fp:
            before = fp.read()

        with patch.object(dao, "_read_cache_once", side_effect=PermissionError("拒绝访问")):
            dao.add_cache("新题", "B")

        with open(self.path, encoding="utf8") as fp:
            self.assertEqual(fp.read(), before)


if __name__ == "__main__":
    unittest.main()
