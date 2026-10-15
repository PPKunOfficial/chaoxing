import sys

from loguru import logger
from tqdm import tqdm

from api.interaction import is_manual_input_active

tqdm_stream = sys.stderr

# 日志缓冲区，用于在手动答题时缓存后台日志，答题结束后统一输出
log_buffer = []
MAX_LOG_BUFFER_SIZE = 1000


def tqdm_sink(msg):
    if is_manual_input_active():
        if len(log_buffer) < MAX_LOG_BUFFER_SIZE:
            log_buffer.append(msg)
    else:
        if log_buffer:
            for buffered_msg in log_buffer:
                tqdm.write(buffered_msg.rstrip(), file=tqdm_stream)
            log_buffer.clear()
        tqdm.write(msg.rstrip(), file=tqdm_stream)
    tqdm_stream.flush()


logger.remove()
logger.add(tqdm_sink, colorize=True, enqueue=True)
logger.add("chaoxing.log", rotation="10 MB", level="TRACE")
