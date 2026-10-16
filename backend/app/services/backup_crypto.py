"""Portable authenticated backup encryption using a user-provided passphrase."""

import base64
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

BACKUP_FORMAT = "rss-manager-encrypted-v1"
ASSOCIATED_DATA = BACKUP_FORMAT.encode()


def _key(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 12 or len(passphrase) > 256:
        raise ValueError("备份密码长度须为 12 至 256 个字符")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode())


def encrypt_backup(data: dict, passphrase: str) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(12)
    plaintext = json.dumps(data, ensure_ascii=False).encode()
    ciphertext = AESGCM(_key(passphrase, salt)).encrypt(nonce, plaintext, ASSOCIATED_DATA)
    return json.dumps(
        {
            "format": BACKUP_FORMAT,
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }
    ).encode()


def decrypt_backup(content: bytes, passphrase: str | None = None) -> dict:
    try:
        envelope = json.loads(content)
        if not isinstance(envelope, dict):
            raise ValueError("备份内容必须是对象")
        if envelope.get("format") == BACKUP_FORMAT:
            salt = base64.b64decode(envelope["salt"], validate=True)
            nonce = base64.b64decode(envelope["nonce"], validate=True)
            if len(salt) != 16 or len(nonce) != 12:
                raise ValueError("Invalid encryption parameters")
            plaintext = AESGCM(_key(passphrase or "", salt)).decrypt(
                nonce,
                base64.b64decode(envelope["ciphertext"], validate=True),
                ASSOCIATED_DATA,
            )
            envelope = json.loads(plaintext)
        elif "format" in envelope:
            raise ValueError("不支持的备份格式")
        # Retain read compatibility with existing unencrypted backups.
        if not isinstance(envelope, dict) or not isinstance(envelope.get("feeds"), list):
            raise ValueError("无效的备份内容")
        return envelope
    except (ValueError, KeyError, TypeError, InvalidTag, UnicodeDecodeError) as exc:
        raise ValueError("备份无效、密码错误或文件已损坏") from exc
