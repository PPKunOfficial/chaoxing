# -*- coding:utf-8 -*-
"""登录使用的 AES-CBC 加密。

只整理字节聚合方式，分组、填充与 base64 文本形态保持协议要求不变。
"""
import base64

import pyaes

from api.config import GlobalConst as gc


def pkcs7_unpadding(string):
    return string[0: -ord(string[-1])]


def pkcs7_padding(s, block_size=16):
    bs = block_size
    return s + (bs - len(s) % bs) * chr(bs - len(s) % bs).encode()


def split_to_data_blocks(byte_str, block_size=16):
    length = len(byte_str)
    j, y = divmod(length, block_size)
    blocks = []
    shenyu = j * block_size
    for i in range(j):
        start = i * block_size
        end = (i + 1) * block_size
        blocks.append(byte_str[start:end])
    stext = byte_str[shenyu:]
    if stext:
        blocks.append(stext)
    return blocks


class AESCipher:
    def __init__(self):
        self.key = str(gc.AESKey).encode("utf8")
        self.iv = str(gc.AESKey).encode("utf8")

    def encrypt(self, plaintext: str) -> str:
        cbc = pyaes.AESModeOfOperationCBC(self.key, self.iv)
        blocks = split_to_data_blocks(pkcs7_padding(plaintext.encode("utf-8")))
        # CBC 逐块顺序加密，聚合结果与逐次拼接的 bytes 完全一致。
        ciphertext = b"".join(cbc.encrypt(block) for block in blocks)
        return base64.b64encode(ciphertext).decode("utf8")

    # def decrypt(self, ciphertext: str):
    #     cbc = pyaes.AESModeOfOperationCBC(self.key, self.iv)
    #     ciphertext.encode('utf8')
    #     ciphertext = base64.b64decode(ciphertext)
    #     ptext = b""
    #     for b in split_to_data_blocks(ciphertext):
    #         ptext = ptext + cbc.decrypt(b)
    #     return pkcs7_unpadding(ptext.decode())
