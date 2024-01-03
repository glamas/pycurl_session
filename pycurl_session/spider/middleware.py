# coding: utf-8

import time
import json
from urllib.parse import urlparse

from pycurl_session.response import Response
from pycurl_session.spider.spider import Spider
from pycurl_session.spider.request import Request
from pycurl_session.spider.robotstxtparser import RobotFileParser
from pycurl_session.spider.exceptions import IgnoreRequest, RetryRequest


class Statistics:
    def __init__(self):
        self.url_collector = set()
        self.stat = {"time_start": time.time(), "time_end": None, "time_used": None}

    def section_count(self, section, code=None):
        if code:
            key = "{0}/{1}".format(section, code)
        else:
            key = "{0}".format(section)
        if key not in self.stat:
            self.stat.update({key: 1})
        else:
            self.stat[key] += 1

    def add_url(self, url, method="GET", callback_name="", spider=""):
        method = method.upper()
        key = "method_count/{0}".format(method)
        url_key = (method, url, callback_name, spider)
        if url_key not in self.url_collector:
            self.url_collector.add(url_key)
        self.section_count(key)

    def in_collection(self, url, method="GET", callback_name="", spider=""):
        if method.upper() == "GET":
            return (method, url, callback_name, spider) in self.url_collector
        else:
            return False

    def process_request(self, request, spider):
        url = request.url
        method = request.method
        callback_name = request.callback.__name__
        spider_id = spider.spider_id
        if (
            self.in_collection(
                url, method=method, callback_name=callback_name, spider=spider_id
            )
            and request.dont_filter == False
        ):
            spider.log("url duplicate: {0}".format(url))
            raise IgnoreRequest()
        else:
            self.add_url(
                url, method=method, callback_name=callback_name, spider=spider_id
            )
            return None

    def process_response(self, request, response, spider):
        self.section_count("status_count", response.status_code)

    def process_exception(self, request, exception, spider):
        logger = spider._get_logger()
        if exception.errno == 28:
            self.section_count("timeout_count", exception.errno)
            logger.error("Timeout ({0}, {1}) when <{2} {3}>".format(
                exception.errno, exception.errmsg, request.method, request.url
            ))
            raise RetryRequest()
        else:
            self.section_count("error_count", exception.errno)
            logger.error( "Error ({0}, {1}) when <{2} {3}>".format(
                    exception.errno, exception.errmsg, request.method, request.url
            ))
            return None

    def process_logstat(self):
        self.stat["time_end"] = time.time()
        self.stat["time_used"] = int((self.stat["time_end"] - self.stat["time_start"]) * 1000) / 1000
        self.stat["time_end"] = "{0}.{1}".format(
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.stat["time_end"])),
            int(self.stat["time_end"] * 1000) % 1000
        )
        self.stat["time_start"] = "{0}.{1}".format(
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.stat["time_start"])),
            int(self.stat["time_start"] * 1000) % 1000
        )
        return self.stat


class RobotsTxt:
    def __init__(self):
        self.data = {}
        self.data_state = {}  # [new, pending, done]
        self.data_url = {}

    def parse_robotstxt(self, response):
        url_robotstxt = response.request["url"]
        key = self.get_key(url_robotstxt)
        rp = RobotFileParser()
        rp.parse(response.text)
        self.data.update({key: rp})
        self.data_state[key] = "done"
        if response.status_code == 404:
            self.data_url.update({key: 404})
        else:
            self.data_url.update({key: url_robotstxt})

    def get_key(self, url):
        url_parsed = urlparse(url)
        scheme = url_parsed.scheme
        hostname = url_parsed.hostname
        port = url_parsed.port
        if url_parsed.port is None:
            if url_parsed.scheme.lower() == "https":
                port = 433
            else:
                port = 80
        return "{0}_{1}_{2}".format(scheme, hostname, port)

    def process_request(self, request, spider):
        url = request.url
        url_parsed = urlparse(url)
        url_domain = url_parsed.netloc

        robots_txt_key = self.get_key(url)
        # new domain, get robots.txt
        if robots_txt_key not in self.data_state:
            url_robotstxt = (
                url[: url.find(url_domain) + len(url_domain)]
                + "/robots.txt"
            )
            robots_item = Request(
                url=url_robotstxt,
                callback=self.parse_robotstxt,
                meta={"robots.txt": True},
                headers={"referer": None},
            )
            self.data_state.update({robots_txt_key: "pending"})
            return robots_item

        # wait for robots.txt done
        if self.data_state[robots_txt_key] == "pending":
            if not request.meta.get("robots.txt"):
                return Response()

        # check url, if robots.txt disallow, raise Exception
        if self.data_state[robots_txt_key] == "done":
            headers = {}
            if "headers" in request.args:
                headers = request.args["headers"]
            user_agent = spider.settings["DEFAULT_HEADERS"]["user-agent"]
            for k, v in headers.items():
                if "user-agent" == k.lower():
                    user_agent = v
            result = self.data[robots_txt_key].can_fetch(user_agent, url)
            if result == False:
                logger = spider._get_logger()
                logger.warning("robots.txt Disallow URL: {0}".format(url))
                raise IgnoreRequest()
        return None

    def process_logstat(self):
        return {"robots.txt": self.data_url}


class Cookies:
    def process_response(self, request, response, spider):
        if spider.settings["COOKIES_DEBUG"]:
            msg = ""
            msg += "Cookies debug for {0} :\nrequest cookies:".format(request.url)
            for k, v in request.cookies.items():
                msg += "\n\t{0}: {1}".format(k, v)

            msg += "\nresponse cookies:".format(response.url)
            for header in response.headers:
                if "set-cookie" in header.lower():
                    msg += "\n\t{0}".format(header)
            spider._get_logger().debug(msg + "\n")
        return None