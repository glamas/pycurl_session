# coding: utf-8

import platform
try:
    import redis
    _REDIS_INSTALLED = True
except ModuleNotFoundError:
    _REDIS_INSTALLED = False
import socket
import time
from collections import deque, namedtuple

from pycurl_session.spider.request import Request
from pycurl_session.spider.spider import Spider, RedisSpider


TaskItem = namedtuple("TaskItem", ["spider_id", "item"])

class Task(object):
    name = "spider.Task"

    def __init__(self, spider:Spider):
        # self.get_last_time = time.time()
        self.spider = spider
        self.queue = deque()

        self.redis_server = None
        self.redis_key = None
        self.redis_key_type = None
        self.redis_encoding = None

        if hasattr(spider, "start_requests"):
            gen_func = spider.start_requests()
            self.queue.append(TaskItem(self.spider.spider_id, gen_func))
        elif hasattr(spider, "start_urls"):
            for url in spider.start_urls:
                request = Request(url=url, callback=spider.parse, headers={"referer": None})
                self.queue.append(TaskItem(self.spider.spider_id, request))
        if isinstance(spider, RedisSpider):
            if not _REDIS_INSTALLED:
                raise Exception("python redis not install(for pip: pip install redis)")
            self.set_redis(spider)

    def get(self):
        if len(self.queue) > 0:
            item = self.queue.popleft()
            return item
        if isinstance(self.spider, RedisSpider):
            key = self.get_redis_key()
            if self.redis_key_type == "set":
                url = self.redis_server.spop(key)
            elif self.redis_key_type == "list":
                url = self.redis_server.lpop(key)
            if url:
                if self.redis_encoding:
                    url = url.decode(self.redis_encoding)
                request = Request(url=url, callback=self.spider.parse, headers={"referer": None})
                request.origin_url = url
                if hasattr(self.spider, "init_request"):
                    # can modify request when RedisSpider has init_request()
                    self.spider.init_request(request)
                return TaskItem(self.spider.spider_id, request)
        return None

    def put(self, spider_id, url):
        if (hasattr(self, "spider")
            and hasattr(self.spider, "spider_id")
            and self.spider.spider_id == spider_id
            and hasattr(self, "redis_server")
            and isinstance(self.redis_server, (redis.Redis, redis.StrictRedis))
        ):
            key = self.get_redis_key()
            if self.redis_key_type == "set":
                self.redis_server.sadd(key, url)
            elif self.redis_key_type == "list":
                self.redis_server.lpush(key, url)

    def set_redis(self, spider):
        if hasattr(spider, "REDIS_HOST") and spider.REDIS_HOST:
            server_host = spider.REDIS_HOST
        else:
            raise Exception("{0} need to set {1}".format(self.spider.spider_id, "REDIS_HOST"))
        if hasattr(spider, "REDIS_PORT") and spider.REDIS_PORT:
            server_port = spider.REDIS_PORT
        else:
            server_port = 6379
        if hasattr(spider, "REDIS_PASSWORD") and spider.REDIS_PASSWORD:
            server_password = spider.REDIS_PASSWORD
        else:
            server_password = None
        if hasattr(spider, "REDIS_DB") and spider.REDIS_DB:
            server_db = spider.REDIS_DB
        else:
            server_db = 0
        if hasattr(spider, "REDIS_ENCODING") and spider.REDIS_ENCODING:
            self.redis_encoding = spider.REDIS_ENCODING
        if hasattr(spider, "REDIS_SSL") and spider.REDIS_SSL:
            server_ssl = True if spider.REDIS_SSL else False
        else:
            server_ssl = False
        if platform.system() == "Windows":
            socket_keepalive_options = None
        else:
            socket_keepalive_options = {
                socket.TCP_KEEPIDLE: 120,
                socket.TCP_KEEPCNT: 3,
                socket.TCP_KEEPINTVL: 5
            }
        self.redis_server = redis.StrictRedis(
            host=server_host,
            password=server_password,
            port=server_port,
            db=server_db,
            ssl=server_ssl,
            socket_keepalive=True,
            socket_connect_timeout=60,
            socket_keepalive_options=socket_keepalive_options,
            )
        key = self.get_redis_key()
        self.redis_key_type = self.redis_server.type(key)
        if "b" == str(self.redis_key_type)[0]:
            self.redis_key_type = self.redis_key_type.decode("utf-8")
        # self.get_last_time = time.time()

    def get_redis_key(self):
        if hasattr(self.spider, "REDIS_START_URLS_KEY") and self.spider.REDIS_START_URLS_KEY:
            self.redis_key = self.spider.REDIS_START_URLS_KEY
        else:
            raise Exception("{0} need to set {1}".format(self.spider.spider_id, "REDIS_START_URLS_KEY"))
        return self.redis_key
