# coding: utf-8

import json
import unittest
from pycurl_session import Session, Response, Selector


class ResponseTestCase(unittest.TestCase):
    def setUp(self):
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
        }
        self.session = Session()
        self.session.headers.update(headers)

    def test_selector(self):
        html = "<html><p>hello</p><p>world</p></html>"
        sel = Selector(text=html)
        result = sel.xpath("//p/text()").getall()
        self.assertEqual(result, ["hello", "world"])

    def test_response_json(self):
        url = "https://httpbin.org/get"
        rsp = self.session.get(url)
        data = rsp.json()
        self.assertEqual(data["url"], url)

    def tearDown(self):
        self.session.clear_cookies()
