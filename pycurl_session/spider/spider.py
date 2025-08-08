# coding: utf-8

from pycurl_session import ColoredConsoleHandler
from pycurl_session.spider.request import Request

import logging


class Spider(object):
    name = "spider"

    def __init__(self):
        self.start_urls = []

    def init_spider(self):
        # do some work with self._session and self.settings
        # which can not touch when __init__()
        pass

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
            ch = ColoredConsoleHandler()
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
    REDIS_DB = 0
    REDIS_SSL = False
    REDIS_START_URLS_KEY = ""
    REDIS_ENCODING = "utf-8" # latin1
    # if set True, origin_url will attach to every request start from it.
    # if set False, only the request made from redis url will attach origin_url.
    # if request.meta has "url_persist" and its value is False, end attach to new request.
    # when raise KeyboardInterrupt, request which has origin_url will put back to redis.
    URL_PERSIST = True

    def init_request(self, req: Request):
        req.callback = self.parse