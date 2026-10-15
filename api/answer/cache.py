# -*- coding: utf-8 -*-
"""答案缓存：JSON 文件的读取、损坏恢复与原子写入。"""
import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

from api.logger import logger

# 同一缓存文件在所有实例间共用一把锁: 读-改-写必须串行, 否则并发写会互相覆盖
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _LOCKS[key] = lock
        return lock


class CacheDAO:
    """
    @Author: SocialSisterYi
    @Reference: https://github.com/SocialSisterYi/xuexiaoyi-to-xuexitong-tampermonkey-proxy
    """
    DEFAULT_CACHE_FILE = "cache.json"
    READ_RETRY_TIMES = 5
    READ_RETRY_INTERVAL = 0.05

    def __init__(self, file: str = DEFAULT_CACHE_FILE):
        self.cache_file = Path(file)
        self._lock = _lock_for(self.cache_file)
        if not self.cache_file.is_file():
            self._write_cache({})

    def _read_cache(self) -> Optional[dict]:
        """读取缓存; 持续读取失败时返回 None, 由调用方按"缓存不可用"处理。

        以前把任何异常都吞成"空缓存", 于是后续写入会把整表覆盖掉; 这里只对
        文件不存在与内容损坏按空缓存继续, 其他 IO 失败有限重试后返回 None。
        """
        last_error = None
        for attempt in range(self.READ_RETRY_TIMES):
            try:
                return self._read_cache_once()
            except OSError as exc:
                last_error = exc
                if attempt + 1 < self.READ_RETRY_TIMES:
                    time.sleep(self.READ_RETRY_INTERVAL)
        logger.error(f"缓存文件读取失败, 已重试 {self.READ_RETRY_TIMES} 次: {last_error}")
        return None

    def _read_cache_once(self) -> dict:
        # 新增缓存文件读取的异常处理
        try:
            with self._lock:
                if not self.cache_file.is_file():
                    return {}
                try:
                    with self.cache_file.open("r", encoding="utf8") as fp:
                        data = json.load(fp)
                    if not isinstance(data, dict):
                        # 语法合法但根节点不是对象(如 [1]): 后续 data.get/data[key] 会抛
                        # AttributeError 或 TypeError, 因此按内容损坏走备份与重建
                        raise json.JSONDecodeError("缓存根节点不是 JSON 对象", "", 0)
                    return data
                except json.JSONDecodeError as e:
                    logger.error(f"缓存文件 JSON 解析失败: {e}, 尝试恢复...")
                    # 尝试从原始二进制中以 utf-8 忽略错误地恢复有效 JSON 段
                    try:
                        raw = self.cache_file.read_bytes()
                        text = raw.decode("utf-8", errors="ignore")
                        start = text.find('{')
                        end = text.rfind('}')
                        if start != -1 and end != -1 and start < end:
                            try:
                                return json.loads(text[start:end + 1])
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # 若无法恢复，备份损坏文件并返回空缓存
                    try:
                        bak_name = f"{self.cache_file.name}.bak.{int(time.time())}"
                        bak_path = self.cache_file.with_name(bak_name)
                        shutil.copy2(self.cache_file, bak_path)
                        logger.error(f"缓存文件已损坏，已备份为: {bak_path}，将使用空缓存继续运行")
                    except Exception as ex:
                        logger.error(f"备份损坏缓存失败: {ex}")
                    return {}
                except UnicodeDecodeError as e:
                    logger.error(f"缓存文件编码读取失败: {e}, 采用恢复策略...")
                    try:
                        raw = self.cache_file.read_bytes()
                        text = raw.decode("utf-8", errors="ignore")
                        start = text.find('{')
                        end = text.rfind('}')
                        if start != -1 and end != -1 and start < end:
                            try:
                                return json.loads(text[start:end + 1])
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        bak_name = f"{self.cache_file.name}.bak.{int(time.time())}"
                        bak_path = self.cache_file.with_name(bak_name)
                        shutil.copy2(self.cache_file, bak_path)
                        logger.error(f"缓存文件编码错误，已备份为: {bak_path}，将使用空缓存继续运行")
                    except Exception as ex:
                        logger.error(f"备份损坏缓存失败: {ex}")
                    return {}
        except OSError:
            # 交由 _read_cache 重试, 不在这里吞成空缓存
            raise
        except Exception as e:
            logger.error(f"读取缓存异常: {e}")
            return {}

    def _write_cache(self, data: dict) -> None:
        # 为缓存写入加锁，防止并发写入损坏文件
        try:
            with self._lock:
                parent = self.cache_file.parent
                if not parent.exists():
                    parent.mkdir(parents=True, exist_ok=True)
                # 写入临时文件后原子替换，减少并发写入时的损坏风险
                fd, tmp_path = tempfile.mkstemp(prefix=self.cache_file.name, dir=str(parent))
                try:
                    with os.fdopen(fd, "w", encoding="utf8") as fp:
                        json.dump(data, fp, ensure_ascii=False, indent=4)
                        fp.flush()
                        os.fsync(fp.fileno())
                    os.replace(tmp_path, str(self.cache_file))
                except Exception as e:
                    # 清理临时文件
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass
                    logger.error(f"Failed to write cache atomically: {e}")
        except IOError as e:
            logger.error(f"Failed to write cache: {e}")

    def get_cache(self, question: str) -> Optional[str]:
        data = self._read_cache()
        if data is None:
            # 缓存不可用按未命中处理, 交给题库继续查询
            return None
        return data.get(question)

    def add_cache(self, question: str, answer: str) -> None:
        # 读-改-写在共享锁内完成，防止并发写入丢更新
        with self._lock:
            data = self._read_cache()
            if data is None:
                logger.error(f"缓存不可用, 已跳过本次写入以免覆盖整表: {question}")
                return
            data[question] = answer
            self._write_cache(data)
