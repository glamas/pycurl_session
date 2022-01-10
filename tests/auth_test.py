# coding: utf-8

import json
import unittest
from pycurl_session import Session, Response, Selector
import pycurl_session.auth as Auth


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
        }
        self.session = Session()
        self.session.headers.update(headers)

    def tearDown(self):
        self.session.clear_cookies()

    def test_httpauth_bearer(self):
        bearer = "example string"
        url = "https://httpbin.org/bearer"
        rsp = self.session.get(url)
        self.assertEqual(rsp.status_code, 401)
        rsp = self.session.get(url, auth=Auth.HTTPAUTH_BEARER(bearer))
        self.assertEqual(rsp.json()["token"], bearer)
        self.assertTrue(rsp.json()["authenticated"])
        rsp = self.session.get(url)
        self.assertEqual(rsp.json()["token"], bearer)
        self.assertTrue(rsp.json()["authenticated"])

    def test_httpauth_basic(self):
        username = "example username"
        password = "example password"
        url = "https://httpbin.org/basic-auth/{0}/{1}".format(username, password)
        rsp = self.session.get(url)
        self.assertEqual(rsp.status_code, 401)
        rsp = self.session.get(url, auth=Auth.HTTPAUTH_BASIC(username, password))
        self.assertEqual(rsp.json()["user"], username)
        self.assertTrue(rsp.json()["authenticated"])
        rsp = self.session.get(url)
        self.assertEqual(rsp.json()["user"], username)
        self.assertTrue(rsp.json()["authenticated"])

    @unittest.skip("skipping")
    def test_httpauth_digest(self):
        username = "example username"
        password = "example password"
        url = "https://httpbin.org/digest-auth/auth/{0}/{1}".format(username, password)
        rsp = self.session.get(url)
        self.assertEqual(rsp.status_code, 401)
        rsp = self.session.get(url, auth=Auth.HTTPAUTH_DIGEST(username, password))
        print(rsp.text)