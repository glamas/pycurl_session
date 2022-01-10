# -*- coding: UTF-8 -*-

import base64
from Crypto.Cipher import AES
from jsbn import RSAKey


################################################################################
#   Crypto
################################################################################
def AES_decrypt(key, data, charset="utf8"):
    decrypt_key = bytes(str(key), charset)
    b64_data = base64.urlsafe_b64decode(data)
    cipher = AES.new(decrypt_key, AES.MODE_ECB)
    decrypted_data = cipher.decrypt(b64_data)
    paddingLen = decrypted_data[len(decrypted_data) - 1]
    decrypted_data = decrypted_data[0:-paddingLen].decode(charset)
    return decrypted_data


def AES_encrypt(key, data, charset="utf8"):
    encrypt_key = bytes(str(key), charset)
    encrypt_data = bytes(str(data), charset)
    BS = 16
    paddingLen = BS - len(encrypt_data) % BS
    if paddingLen != 0:
        encrypt_data = encrypt_data + bytes(chr(paddingLen) * paddingLen, charset)
    cipher = AES.new(encrypt_key, AES.MODE_ECB)
    encrypt_data = cipher.encrypt(encrypt_data)
    encrypt_data = base64.urlsafe_b64encode(encrypt_data)
    encrypt_data = encrypt_data.decode("utf8")
    return encrypt_data.replace("_", "/").replace("-", "+")


################################################################################
#   jsbn
################################################################################
def smt_jsbn(text, publickey="", e="10010"):
    rsa = RSAKey()
    rsa.setPublic(publickey, e)
    return rsa.encrypt(text)
