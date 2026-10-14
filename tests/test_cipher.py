# -*- coding: utf-8 -*-
"""登录加密的字节级回归：固定输入必须产生固定密文。

密文常量取自等价重构前的实现，用于锁定 AES-CBC + PKCS7 + base64 的协议字节。
"""
import unittest

from api.cipher import AESCipher, pkcs7_padding, split_to_data_blocks


class CipherGoldenTest(unittest.TestCase):
    # 覆盖空串、单分组、整分组边界与多分组非 ASCII 输入
    GOLDEN = {
        "": "LXYPGIOJyFUvuG1SPO0nVQ==",
        "13800138000": "yYcVatS+4J+JGnm88UM56A==",
        "a" * 16: "YaUb/y6VdOUq8BImCZkv2KHpF+lcIDY7wyzg3Njg5CU=",
        "密码password!": "XbWm2UyRdfmZEDwsZOCOBA==",
        "x" * 100: (
            "DgLcwyHZOsS1g8ETeXyY5rdnjwxGZWTIXuvP99xxvy0ASSYG09x87ozb/UIEilbdG3v+H"
            "I6fsZoi8bFz3CJUrbEL7Rk5RcVY0wWp7+YngUH6wZGP/yWrYGi+IVQ1g8cDgH8z3J3yvg"
            "czz8QvdtfVUA=="
        ),
    }

    def test_golden_ciphertext(self):
        cipher = AESCipher()
        for plaintext, expected in self.GOLDEN.items():
            with self.subTest(plaintext=plaintext):
                self.assertEqual(cipher.encrypt(plaintext), expected)

    def test_encrypt_is_deterministic(self):
        cipher = AESCipher()
        self.assertEqual(cipher.encrypt("same-input"), cipher.encrypt("same-input"))


class PaddingAndBlockTest(unittest.TestCase):
    def test_pkcs7_padding_always_adds_a_block(self):
        self.assertEqual(pkcs7_padding(b""), b"\x10" * 16)
        self.assertEqual(pkcs7_padding(b"a" * 15), b"a" * 15 + b"\x01")
        self.assertEqual(pkcs7_padding(b"a" * 16), b"a" * 16 + b"\x10" * 16)

    def test_split_keeps_trailing_partial_block(self):
        self.assertEqual(split_to_data_blocks(b""), [])
        self.assertEqual([len(b) for b in split_to_data_blocks(b"a" * 16)], [16])
        self.assertEqual([len(b) for b in split_to_data_blocks(b"a" * 20)], [16, 4])


if __name__ == "__main__":
    unittest.main()
