# coding: utf-8

from pycurl_session.spider.request import Request

import logging


class Spider(object):
    name = "spider"

    def __init__(self):
        self.start_urls = []

    # def start_request(self):
    #     pass

    def parse(self, response):
        pass

    def _get_logger(self):
        logger = logging.getLogger(self.spider_id)
        if len(logger.handlers) == 0:
            if hasattr(self, "settings") and "LOG_FORMAT" in self.settings:
                log_format = self.settings["LOG_FORMAT"]
            else:
                log_format = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            ch.setLevel(logging.DEBUG)
            logger.addHandler(ch)
        return logger

    @property
    def spider_id(self):
        return ".".join([self.__class__.__name__, str(self.name)])

    def log(self, msg):
        logger = self._get_logger()
        logger.info(msg)

    def closed(self, reason):
        pass

class RedisSpider(Spider):
    name = "RedisSpider"
    REDIS_HOST = ""
    REDIS_PORT = 6379
    REDIS_PASSWORD = ""
    # REDIS_URL = "" # e.g. redis://user:pass@hostname:9001, use this first
    REDIS_START_URLS_KEY = ""
    REDIS_ENCODING = "utf-8" # latin1

    def __init__(self):
        # no start_urls
        pass

    def init_request(self, req: Request):
        req.callback = self.parse