# coding: utf-8

import os
import sys
import importlib
import json
import logging
import platform
import time
import gc

from collections import deque
from copy import deepcopy, copy
from inspect import isgenerator
from urllib.parse import urlparse

import pycurl
from pycurl_session import Session, ColoredConsoleHandler
from pycurl_session.response import Response
from pycurl_session.spider import settings
from pycurl_session.spider.exceptions import IgnoreRequest, DropItem, CloseSpider, PerformError, RetryRequest
from pycurl_session.spider.middleware import Statistics, RobotsTxt, CookiesDebug
from pycurl_session.spider.request import Request
from pycurl_session.spider.task import TaskItem, Task


class Schedule(object):
    name = "Schedule"

    def __init__(self, custom_settings={}):
        self.init_success = True
        self.logstat = {}

        self.settings = {}
        self.update_settings(custom_settings)

        self.set_logger(self.name)
        self.logger = logging.getLogger(self.name)

        self.session = Session(self.settings["BOT"], self.settings["COOKIES_STORE_ENABLED"])
        self.session.headers.update(self.settings["DEFAULT_HEADERS"])
        if self.settings["SIMULATE_FETCH"]:
            self.session.simulate_fetch = True
        self.session.set_timeout(self.settings["DOWNLOAD_TIMEOUT"])
        if self.settings["COOKIES_STORE_ENABLED"] and self.settings["COOKIES_STORE_DB"]:
            self.session.set_cookie_db(self.settings["COOKIES_STORE_DB"])

        self.multi_cookiejar = {}
        self.set_multi_cookiejar(self.settings["BOT"])

        self.cm = pycurl.CurlMulti()
        self.queue_pending = deque()
        self.queue_delay = deque()
        self.queue_pending_item = None
        self.curl_pool = deque()
        self.curl_pool_max = max(16, self.settings["CONCURRENT_REQUESTS"] * 2)
        self.curl_handles = {}
        self.num_handles = 0    # running handle count

        self.spider_instance = {}
        self.spider_task = {}
        self.spider_task_done = set()
        self.middleware = []
        self.pipeline = []
        self.spider_close_reason = {}

        self.robotstxt = RobotsTxt()
        self.set_middleware()
        self.set_pipeline()

        self.response_ref = {}

    def update_settings(self, custom_settings):
        for item in dir(settings):
            if item.isupper():
                self.settings.update({item: getattr(settings, item)})
        for k, v in custom_settings.items():
            if item not in self.settings:
                self.settings.update({k: v})
            elif isinstance(self.settings[k], dict):
                self.settings[k].update(v)
            else:
                self.settings[k] = v
        headers = settings.DEFAULT_HEADERS
        if "DEFAULT_HEADERS" in custom_settings:
            for k, v in custom_settings["DEFAULT_HEADERS"].items():
                headers.update({k.lower(): v})
        if (
            "USER_AGENT" in custom_settings
            and headers["user-agent"] == settings.USER_AGENT
        ):
            headers["user-agent"] = custom_settings["USER_AGENT"]
        self.settings["DEFAULT_HEADERS"] = headers
        if self.settings["CONCURRENT_REQUESTS"] <= 0:
            self.settings["CONCURRENT_REQUESTS"] = 1

    def set_logger(self, name):
        logger = logging.getLogger(name)
        if len(logger.handlers) == 0:
            formatter = logging.Formatter(
                self.settings["LOG_FORMAT"], datefmt="%Y-%m-%d %H:%M:%S",
            )
            logger.setLevel(logging.DEBUG)
            ch = ColoredConsoleHandler()
            ch.setFormatter(formatter)
            ch.setLevel(logging.DEBUG)
            logger.addHandler(ch)
            if self.settings["LOG_ENABLED"] and self.settings["LOG_FILE"]:
                dir_path = os.path.dirname(self.settings["LOG_FILE"])
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)
                fh = logging.FileHandler(
                    filename=self.settings["LOG_FILE"],
                    encoding=self.settings["LOG_ENCODING"],
                )
                fh.setLevel(logging.DEBUG)
                fh.setFormatter(formatter)
                logger.addHandler(fh)

    def set_multi_cookiejar(self, cookiejar=None):
        if cookiejar and cookiejar not in self.multi_cookiejar:
            self.multi_cookiejar.update({cookiejar: 1})
            if self.settings["COOKIES_CLEAR"]:
                self.session.clear_cookies(cookiejar)

    def set_middleware(self):
        # default middleware
        self.middleware.append(Statistics())
        self.middleware.append(CookiesDebug())
        if "DOWNLOADER_MIDDLEWARES" not in self.settings:
            self.settings.update({"DOWNLOADER_MIDDLEWARES": []})

        # DOWNLOADER_MIDDLEWARES
        for imp in self.settings["DOWNLOADER_MIDDLEWARES"]:
            try:
                if "." in imp:
                    m = imp.split(".")
                    c = m[-1]
                    p = ".".join(m[:-1])
                else:
                    p = os.path.split(sys.argv[0])[-1].split(".")[0]
                    c = imp
                middleware = getattr(importlib.import_module(p), c, None)
                if middleware:
                    self.middleware.append(middleware())
                else:
                    raise Exception("DOWNLOADER_MIDDLEWARES not found: {0}".format(imp))
            except Exception as e:
                self.logger.exception(e)
                self.init_success = False

    def set_pipeline(self):
        # default pipeline
        if "ITEM_PIPELINES" not in self.settings:
            self.settings.update({"ITEM_PIPELINES": []})

        # ITEM_PIPELINES
        for imp in self.settings["ITEM_PIPELINES"]:
            try:
                if "." in imp:
                    m = imp.split(".")
                    c = m[-1]
                    p = ".".join(m[:-1])
                else:
                    p = os.path.split(sys.argv[0])[-1].split(".")[0]
                    c = imp
                pipeline = getattr(importlib.import_module(p), c, None)
                if pipeline:
                    self.pipeline.append(pipeline())
                    self.set_logger(imp)
                    setattr(pipeline, "_logger_name", imp)
                else:
                    raise Exception("ITEM_PIPELINES not found: {0}".format(imp))
            except Exception as e:
                self.logger.exception(e)
                self.init_success = False

    def run_pipeline(self, item, spider):
        # only support dict type
        if not isinstance(item, dict): return
        count = "item_pipeline/count"
        if count not in self.logstat:
            self.logstat.update({count: 0})
        self.logstat[count] += 1
        for pipline in self.pipeline:
            if hasattr(pipline, "process_item"):
                try:
                    pipline.process_item(item, spider)
                except DropItem as e:
                    if hasattr(pipline, "_logger_name"):
                        log = logging.getLogger(pipline._logger_name)
                    else:
                        log = self.logger
                    log.info(f"Drop item in spider[{0}] {1}".format(spider.spider_id, e))
                except Exception as e:
                    if hasattr(pipline, "_logger_name"):
                        log = logging.getLogger(pipline._logger_name)
                    else:
                        log = self.logger
                    log.exception(e)

    def add_spider(self, spider, task_provider:Task=Task, **arg):
        spider_name = ".".join([spider.__name__, spider.name])
        try:
            instance = spider(**arg)
        except Exception as e:
            self.logger.error("Add spider [{0}] failed: {1}".format(spider_name, e))
            self.init_success = False
            return
        if not hasattr(instance, "_session"):
            setattr(instance, "_session", self.session)
        if not hasattr(instance, "settings"):
            setattr(instance, "settings", deepcopy(self.settings))
        if hasattr(instance, "init_spider"):
            try:
                instance.init_spider()
            except Exception as e:
                self.logger.error("Spider [{0}] run init_spider() failed: {1}".format(spider_name, e))
                self.init_success = False
                return
        spider_id = instance.spider_id
        self.set_logger(spider_id)
        self.spider_instance.update({spider_id: instance})
        try:
            if not issubclass(task_provider, Task):
                self.logger.error("add_spider() keyword argument 'task_provider' need class Task")
            self.spider_task.update({spider_id: task_provider(instance)})
        except Exception as e:
            self.logger.exception("Add spider [{0}] failed: {1}".format(spider_name, e))
            self.init_success = False
            return

    def get_queue_item(self):
        for spider_id, _ in self.spider_instance.items():
            if spider_id in self.spider_task_done:
                continue
            if spider_id in self.spider_task:
                item = self.spider_task[spider_id].get()
                if item is None:
                    self.spider_task_done.add(spider_id)
                elif isinstance(item, TaskItem):
                    yield item

    def get_curl_pool(self):
        if len(self.curl_pool):
            return self.curl_pool.popleft()
        else:
            return pycurl.Curl()

    def put_curl_pool(self, c):
        c.reset()
        if hasattr(c, "in_pool") and c.in_pool == 1:
            self.session.init_curl_var(c)
            if hasattr(c, "spider_request"): del c.spider_request
            if hasattr(c, "meta"): c.meta.clear()
            if hasattr(c, "top_domain"): c.top_domain = None
            if hasattr(c, "domain"): c.domain = None
            if hasattr(c, "spider_id"): c.spider_id = None
            if len(self.curl_pool) > self.curl_pool_max:
                c.close()
                del c
            else:
                self.curl_pool.append(c)

    def get_pending_taskitem(self):
        return self.queue_pending.popleft()

    def put_pending_taskitem(self, taskitem):
        if self.settings["DEPTH_PRIORITY"]:
            self.queue_pending.appendleft(taskitem)
        else:
            self.queue_pending.append(taskitem)

    def make_curl_handle(self, request, spider):
        url = request.url
        url_parsed = urlparse(url)
        url_domain = url_parsed.netloc
        top_domain = (
            url_domain[url_domain.find(".") :]
            if len(url_domain.split(".")) >= 2
            else url_domain
        )
        if url_domain not in self.curl_handles:
            delay = self.settings["DOWNLOAD_DELAY_DOMAIN"].get(url_domain)
            if not delay: delay = self.settings["DOWNLOAD_DELAY"]
            self.curl_handles.update({url_domain: {"handles": [], "delay": delay, "last": 0}})
        args = {
            "method": request.method,
            "headers": request.headers,
            "cookies": request.cookies,
            "data": request.data,
            "json": request.json,
        }
        meta = request.meta
        if "cookiejar" in meta:
            args.update({"session_id": meta["cookiejar"]})
            self.set_multi_cookiejar(meta["cookiejar"])
        if "proxy" in meta:
            args.update({"proxy": meta["proxy"]})
        if "dont_redirect" in meta and meta["dont_redirect"]:
            args.update({"allow_redirects": False})

        c = self.get_curl_pool()
        c.in_pool = 1
        c = self.session.prepare_curl_handle(url=url, c=c, **args)
        c.meta = meta
        c.top_domain = top_domain
        c.domain = url_domain
        c.spider_id = spider.spider_id
        c.max_retry_times = meta.get("max_retry_times", self.settings["RETRY_TIMES"])
        if meta.get("dont_retry", False):
            c.max_retry_times = 0
        self.session.set_http_version(c, meta.get("http_version", None))

        request.cookies = c.request["cookies"]
        request.headers = c.request["headers"]
        c.spider_request = request
        return c

    def run_request_callback(self, request, response, spider):
        spider_id = spider.spider_id
        try:
            item = request._run_callback(response, **request.cb_kwargs)
        except Exception as e:
            spider._get_logger().exception(e)
            return True
        if isgenerator(item):
            while True:
                try:
                    # get next request and stop or raise
                    if id(item) not in self.response_ref:
                        self.response_ref.update({id(item): {
                            "url": response.request["url"],
                            "origin_url": response.request["origin_url"]
                        }})
                    result = next(item)
                    if isinstance(result, dict):
                        self.run_pipeline(result, spider)
                        continue
                    if isinstance(result, Request):
                        result.headers.update({
                            "referer": response.request["url"]
                        })
                        # new request persist origin_url if:
                        # Spider.URL_PERSIST = True
                        # request.meta has not 'url_persist' or its value is True
                        url_persist = False
                        if (spider_id in self.spider_instance
                            and hasattr(self.spider_instance[spider_id], "URL_PERSIST")
                        ):
                            url_persist = self.spider_instance[spider_id].URL_PERSIST
                        if url_persist:
                            url_persist_in_meta = result.meta.get("url_persist")
                            if url_persist_in_meta is None or url_persist_in_meta:
                                result.origin_url = response.request["origin_url"]
                        self.put_pending_taskitem(TaskItem(spider_id, result))
                        self.put_pending_taskitem(TaskItem(spider_id, item))
                        break
                    # other, ignore
                    continue
                except StopIteration:
                    if id(item) in self.response_ref:
                        self.response_ref.pop(id(item))
                        self.response_ref = copy(self.response_ref)
                    break
                except CloseSpider as reason:
                    self.manual_close_task(spider, reason)
                except Exception as e:
                    self.logger.exception(e)
                break
        return True

    def add_curl_handle(self, c):
        self.cm.add_handle(c)
        self.num_handles += 1
        if c not in self.curl_handles[c.domain]["handles"]:
            self.curl_handles[c.domain]["handles"].append(c)
            self.curl_handles[c.domain]["last"] = time.time()

    def collect_curl_multi(self):
        if len(self.queue_pending) == 0:
            # init self.queue_pending
            try:
                queue_item = next(self.get_queue_item())
                if queue_item:
                    self.put_pending_taskitem(queue_item)
            except StopIteration:
                pass

        # ========== loop start ==========
        self.queue_delay.clear()
        while len(self.queue_pending) > 0:
            if self.num_handles >= self.settings["CONCURRENT_REQUESTS"]:
                break
            queue_item = self.queue_pending.popleft()
            spider_id, item = queue_item.spider_id, queue_item.item
            spider = self.spider_instance[spider_id]
            # record current item.
            # while loop, item must in queue_pending or queue_delay or queue_pending_item
            self.queue_pending_item = queue_item
            if isgenerator(item):
                # ========== process isgenerator start ==========
                while True:
                    try:
                        # get next request and stop or raise
                        result = next(item)
                        if isinstance(result, dict):
                            self.run_pipeline(result, spider)
                            continue
                        if isinstance(result, Request):
                            if id(item) in self.response_ref:
                                result.headers.update({
                                    "referer": self.response_ref[id(item)]["url"]
                                })
                                # new request persist origin_url if:
                                # Spider.URL_PERSIST = True
                                # request.meta has not 'url_persist' or its value is True
                                url_persist = False
                                if (spider_id in self.spider_instance
                                    and hasattr(self.spider_instance[spider_id], "URL_PERSIST")
                                ):
                                    url_persist = self.spider_instance[spider_id].URL_PERSIST
                                if url_persist:
                                    url_persist_in_meta = result.meta.get("url_persist")
                                    if url_persist_in_meta is None or url_persist_in_meta:
                                        result.origin_url = self.response_ref[id(item)]["origin_url"]
                            self.put_pending_taskitem(TaskItem(spider_id, item))
                            self.put_pending_taskitem(TaskItem(spider_id, result))
                            break
                        # other, ignore
                        continue
                    except StopIteration:
                        if id(item) in self.response_ref:
                            self.response_ref.pop(id(item))
                            self.response_ref = copy(self.response_ref)
                        self.queue_pending_item = None
                        del queue_item
                        break
                    except CloseSpider as reason:
                        self.manual_close_task(spider, reason)
                    except Exception as e:
                        self.logger.exception(e)
                    break
                # ========== process isgenerator end ==========
            elif isinstance(item, Request):
                # ========== process request start ==========
                url = item.url
                url_parsed = urlparse(url)
                url_domain = url_parsed.netloc
                if url_domain not in self.curl_handles:
                    delay = self.settings["DOWNLOAD_DELAY_DOMAIN"].get(url_domain)
                    if not delay: delay = self.settings["DOWNLOAD_DELAY"]
                    self.curl_handles.update({
                        url_domain: {"handles": [], "delay": delay, "last": 0}}
                    )
                # ========== RobotsTxt start ==========
                if self.settings["ROBOTSTXT_OBEY"]:
                    # RobotsTxt.process_request:
                    #   Request: put back queue_item, and put robotstxt request item
                    #   Response: downloading, put back queue_item
                    #   None: check url pass, continue
                    # Or raise IgnoreRequest: check url failed, drop queue_item
                    try:
                        ret = self.robotstxt.process_request(item, spider)
                        if isinstance(ret, Request):
                            self.queue_delay.append(TaskItem(spider_id, ret))
                            self.queue_delay.append(TaskItem(spider_id, item))
                            continue
                        if isinstance(ret, Response):
                            self.queue_delay.append(TaskItem(spider_id, item))
                            continue
                    except IgnoreRequest:
                        self.queue_pending_item = None
                        del queue_item
                        continue
                # ========== RobotsTxt end ==========
                if (
                    time.time() - self.curl_handles[url_domain]["last"]
                    >= self.curl_handles[url_domain]["delay"]
                ):
                    # add data to Request, e.g. cookies
                    try:
                        c = self.make_curl_handle(item, spider)
                    except Exception as e:
                        spider._get_logger().error(
                            "Error handle <{0} {1}> (referer: {2})".format(
                                item.method, item.url, item.headers.get("referer")
                            )
                        )
                        spider._get_logger().exception(e)
                        continue

                    # ========== Middleware start ==========
                    get_new_queue_item = False
                    for middleware in self.middleware:
                        if hasattr(middleware, "process_request"):
                            # ret: 
                            #   None: continue, next middleware
                            #   Request: replace old request
                            #   Response: finish request
                            # or raise IgnoreRequest: drop queue_item, break loop
                            try:
                                ret = middleware.process_request(c.spider_request, spider)
                                if ret is None: continue
                                if isinstance(ret, Request):
                                    self.queue_delay.append(TaskItem(spider_id, ret))
                                    get_new_queue_item = True
                                    break
                                if isinstance(ret, Response):
                                    self.run_request_callback(c.spider_request, ret, spider)
                                    get_new_queue_item = True
                                    break
                            except IgnoreRequest:
                                get_new_queue_item = True
                                break
                            except Exception as e:
                                spider._get_logger().exception(e)

                    if get_new_queue_item:
                        self.queue_pending_item = None
                        del queue_item
                        self.put_curl_pool(c)
                        continue
                    # ========== Middleware end ==========
                    self.add_curl_handle(c)
                    del queue_item
                else:
                    self.queue_delay.append(queue_item)
                    self.queue_pending_item = None
                # ========== process request end ==========

            # if all item put to curl or queue_delay,
            # get TaskItem until num_handles hit CONCURRENT_REQUESTS
            if (len(self.queue_pending) == 0
                and self.num_handles < self.settings["CONCURRENT_REQUESTS"]
                # NOTE: queue_delay will quickly increase if TaskItem not put to curl.
                and len(self.queue_delay) < self.settings["CONCURRENT_REQUESTS"] * (len(self.curl_handles.keys()) + 1)
            ):
                try:
                    queue_item = next(self.get_queue_item())
                    if queue_item:
                        self.put_pending_taskitem(queue_item)
                except StopIteration:
                    pass
        # ========== loop start ==========

        # put back to queue_pending
        while len(self.queue_delay) > 0:
            self.queue_pending.appendleft(self.queue_delay.popleft())

    def process_response(self, response, c):
        spider_id = c.spider_id
        spider = self.spider_instance[spider_id]
        perform_time = c.getinfo(pycurl.TOTAL_TIME)
        if response.status_code in self.session.redirect_http_codes and (
            (
                "dont_redirect" not in response.meta
                and self.settings["REDIRECT_ENABLED"] == True
            )
            or (
                "dont_redirect" in response.meta
                and response.meta["dont_redirect"] != True
            )
        ):
            self.cm.remove_handle(c)
            self.session._response_redirect(c, response.status_code, logger_handle=self.logger)
            if self.settings["ROBOTSTXT_OBEY"]:
                # check new url top_domain if robotstxt check enabled
                old_top_domain = c.top_domain
                new_url = c.request["url"]      # update by session._response_redirect()
                url_parsed = urlparse(new_url)
                url_domain = url_parsed.netloc
                new_top_domain = (
                    url_domain[url_domain.find(".") :]
                    if len(url_domain.split(".")) >= 2
                    else url_domain
                )
                if new_top_domain != old_top_domain:
                    # new domain, put back to queue, and delete curl
                    c.spider_request.url = new_url
                    self.queue_pending.appendleft(TaskItem(c.spider_id, c.spider_request))
                    return True
            # put back to running handle
            self.add_curl_handle(c)
            return False
        self.logger.info(
            "({0}) <{1} {2} {3}s> (referer: {4})".format(
                response.status_code,
                c.request["method"],
                c.request["url"],
                perform_time,
                c.request["referer"],
            )
        )
        if response.status_code in self.session.retry_http_codes:
            self.cm.remove_handle(c)
            self.session._response_retry(
                c, logger_handle=self.logger,
            )
            self.add_curl_handle(c)
            if c.retry <= c.max_retry_times:
                return False
        return self.run_request_callback(c.spider_request, response, spider)

    def recycle_curl(self, c, recycle=True):
        if recycle:
            self.cm.remove_handle(c)
            if c in self.curl_handles[c.domain]["handles"]:
                self.curl_handles[c.domain]["handles"].remove(c)
            self.put_curl_pool(c)
        else:
            if c in self.curl_handles[c.domain]["handles"]:
                self.curl_handles[c.domain]["last"] = time.time()

    def process_curl_multi_ok(self, c):
        ret = True  # return True if c is no more use, and can be remove from cm and curl_handles
        spider_id = c.spider_id
        spider = self.spider_instance[spider_id]

        if c in self.curl_handles[c.domain]["handles"]:
            # request finish. can add new c. but if return False, need update.
            self.curl_handles[c.domain]["last"] = time.time()

        response = Response(session=self.session)
        self.session.gather_response(c, response)
        response.meta = deepcopy(c.meta)
        response.headers = deepcopy(c.header_handler.headers)
        response.request.update({"origin_url": c.spider_request.origin_url})

        # ========== Middleware start ==========
        get_new_queue_item = False
        for m_index in range(len(self.middleware), 0, -1):
            middleware = self.middleware[m_index - 1]
            if hasattr(middleware, "process_response"):
                # ret:
                #   None: continue, next middleware
                #   Request: replace old request
                #   Response: finish request
                # or raise IgnoreRequest: drop queue_item, break loop
                try:
                    ret = middleware.process_response(c.spider_request, response, spider)
                    if ret is None: continue
                    if isinstance(ret, Request):
                        self.put_pending_taskitem(TaskItem(spider_id, ret))
                        get_new_queue_item = True
                        break
                    if isinstance(ret, Response):
                        response = ret
                        break
                except IgnoreRequest:
                    get_new_queue_item = True
                    break
                except Exception as e:
                    spider._get_logger().exception(e)
        if get_new_queue_item:
            # new request, no need to process response
            del response
            return ret
        # ========== Middleware end ==========
        # ========== process_response start ==========
        ret = self.process_response(response, c)
        # ret = False means c redirect or retry, keep response and c.
        if ret: del response
        return ret
        # ========== process_response end ==========

    def process_curl_multi_err(self, c, errno, errmsg):
        spider_id = c.spider_id
        spider = self.spider_instance[spider_id]

        # ========== Middleware start ==========
        free_c = True
        get_new_queue_item = False
        for m_index in range(len(self.middleware), 0, -1):
            middleware = self.middleware[m_index - 1]
            if hasattr(middleware, "process_exception"):
                # ret:
                #   None: continue, next middleware
                #   Request: replace old request
                #   Response: finish request
                # or raise RetryRequest: retry request, break loop
                try:
                    ret = middleware.process_exception(c.spider_request, PerformError(errno, errmsg), spider)
                    if ret is None: continue
                    if isinstance(ret, Request):
                        self.put_pending_taskitem(TaskItem(spider_id, ret))
                        get_new_queue_item = True
                        break
                    if isinstance(ret, Response):
                        self.process_response(ret, c)
                        break
                except RetryRequest:
                    c.retry += 1
                    if c.retry <= c.max_retry_times:
                        self.cm.remove_handle(c)
                        self.add_curl_handle(c)
                        free_c = False
                        # middleware control log
                    else:
                        msg = "Failed to process <{0} {1}>, try max time.".format(
                            c.request["method"], c.request["url"]
                        )
                        self.logger.error(msg)
                    break
                except Exception as e:
                    spider._get_logger().exception(e)
        if get_new_queue_item:
            return True
        return free_c
        # ========== Middleware end ==========

    def manual_close_task(self, spider, reason=None):
        spider_id = spider.spider_id
        if spider_id in self.spider_task_done:
            return
        spider.log("{} raise CloseSpider(). No more new request will be added to queue.".format(spider_id))
        self.spider_close_reason.update({spider_id: reason})
        if spider_id in self.spider_task:
            self.spider_task_done.add(spider_id)
            # put back redis if needed
            # queue_pending_item
            if (self.queue_pending_item
                and self.queue_pending_item[0] == spider_id
                and self.queue_pending_item[1].origin_url
            ):
                self.spider_task[spider_id].put(spider_id, self.queue_pending_item[1].origin_url)
                self.queue_pending_item = None
            # queue_pending
            temp_queue = deque()
            while len(self.queue_pending) > 0:
                item = self.queue_pending.popleft()
                if item[0] == spider_id:
                    if item[1].origin_url:
                        self.spider_task[spider_id].put(spider_id, item[1].origin_url)
                else:
                    temp_queue.appendleft(item)
            while len(temp_queue) > 0:
                self.queue_pending.appendleft(temp_queue.popleft())
            # queue_delay
            while len(self.queue_delay) > 0:
                item = self.queue_delay.popleft()
                if item[0] == spider_id:
                    if item[1].origin_url:
                        self.spider_task[spider_id].put(spider_id, item[1].origin_url)
                else:
                    temp_queue.appendleft(item)
            while len(temp_queue) > 0:
                self.queue_delay.appendleft(temp_queue.popleft())


    def process_close_call(self):
        for spider_id, spider in self.spider_instance.items():
            # item pipeline close_spider()
            for pipline in self.pipeline:
                if hasattr(pipline, "close_spider"):
                    try:
                        pipline.close_spider(spider)
                    except Exception as e:
                        if hasattr(pipline, "_logger_name"):
                            log = logging.getLogger(pipline._logger_name)
                        else:
                            log = self.logger
                        log.exception(e)

            # spider closed()
            if hasattr(spider, "closed"):
                reason = "finished"
                try:
                    if spider_id in self.spider_close_reason:
                        reason = self.spider_close_reason[spider_id]
                    spider.closed(reason)
                except Exception as e:
                    spider._get_logger().exception(e)

    def interrupt_rollback_item(self, spider_id=None):
        if self.queue_pending_item:
            self.queue_pending.appendleft(self.queue_pending_item)
        while len(self.queue_delay):
            self.queue_pending.appendleft(self.queue_delay.popleft())
        try:
            while len(self.queue_pending) > 0:
                item = self.queue_pending.popleft()
                if item[0] in self.spider_task and item[1].origin_url:
                    self.spider_task[item[0]].put(item[0], item[1].origin_url)
            count = 0
            for _, item in self.curl_handles.items():
                for c in item["handles"]:
                    if c.spider_id in self.spider_task and c.spider_request.origin_url:
                        self.spider_task[c.spider_id].put(c.spider_id, c.spider_request.origin_url)
                        count += 1
        except Exception as e:
            self.logger.exception(e)

    def run(self):
        if not self.init_success: return
        # ========== schedule info start ==========
        self.logger.info("Schedule started")
        backend_info = {
            "OS": {
                "node": platform.node(),
                "platform": platform.platform(),
                "processor": platform.processor(),
            },
            "Python version": sys.version,
            "PycURL version": pycurl.version_info(),
        }
        self.logger.info("Backend info: {0}".format(backend_info))
        self.logger.info("Overridden settings: {0}".format(self.settings))
        self.logger.info("Enabled spider: {0}".format(list(self.spider_task.keys())))
        self.logger.info("Spider started")
        # ========== schedule info end ==========
        # ========== main loop start ==========
        init_time = time.time()
        gc_time = init_time
        per_min_time = init_time
        per_min_item_last = 0
        per_min_item_total = 0
        per_min_page = 0
        per_min_page_total = 0

        loop_init = True
        to_update_cm = True
        running_handles = 0
        while loop_init or self.num_handles > 0 or len(self.queue_pending) > 0:
            loop_init = False
            try:
                while 1:
                    ret, self.num_handles = self.cm.perform()
                    if ret != pycurl.E_CALL_MULTI_PERFORM or self.num_handles == 0:
                        break
                self.cm.select(0.01)

                if time.time() - per_min_time > 60:
                    per_min_time = time.time()
                    per_min_page_total += per_min_page
                    per_min_item_total = self.logstat.get("item_pipeline/count", 0)
                    self.logger.info("Crawled {0} pages and handle {1} items (last minute {2} pages and {3} items), passed {4} minites".format(
                        per_min_page_total,
                        per_min_item_total,
                        per_min_page,
                        per_min_item_total - per_min_item_last,
                        int((per_min_time - init_time) / 60)
                    ))
                    per_min_item_last = per_min_item_total
                    per_min_page = 0

                if running_handles != self.num_handles:
                    running_handles = self.num_handles
                    num_q, ok_list, err_list = self.cm.info_read()
                    for c in ok_list:
                        recycle = self.process_curl_multi_ok(c)
                        self.recycle_curl(c, recycle)
                        per_min_page += 1

                    for c, errno, errmsg in err_list:
                        recycle = self.process_curl_multi_err(c, errno, errmsg)
                        self.recycle_curl(c, recycle)
                        per_min_page += 1

                    if time.time() - gc_time > 60:
                        gc_time = time.time()
                        gc.collect()

                # when to add new curl?
                if (to_update_cm
                    and running_handles <= self.settings["CONCURRENT_REQUESTS"]
                    # and len(self.queue_pending) <= self.settings["CONCURRENT_REQUESTS"]
                ):
                    self.collect_curl_multi()
                # when Ctrl+c, wait for running_handles to be 0
                if to_update_cm == False and running_handles == 0:
                    break
            except KeyboardInterrupt:
                if to_update_cm == True:
                    to_update_cm = False
                    self.logger.info(
                        "KeyboardInterrupt raised. "
                        "No more new request will be added to queue. "
                        "You can send CTRL-c again to shut down schedule. "
                        "Or wait for request done."
                    )
                    # fix: when first send CTRL-c, put item back if needed
                    self.interrupt_rollback_item()
                    continue
                else:
                    for spider_id, _ in self.spider_instance.items():
                        if spider_id not in self.spider_close_reason:
                            self.spider_close_reason.update({spider_id: "shutdown"})
                    break
        # ========== main loop end ==========

        # all spider done, spider call closed() and item pipeline call close_spider()
        self.process_close_call()

        # some clean work. may be usefull
        self.queue_pending.clear()
        self.queue_delay.clear()
        self.curl_pool.clear()
        self.curl_handles.clear()
        self.response_ref.clear()   # important
        self.cm.close()
        self.spider_task.clear()

        # ========== logstat start ==========
        if self.settings["ROBOTSTXT_OBEY"]:
            self.logstat.update(self.robotstxt.process_logstat())
        for middleware in self.middleware:
            if hasattr(middleware, "process_logstat"):
                self.logstat.update(middleware.process_logstat())
        self.logger.info("Dumping logstat:\n" + json.dumps(self.logstat, sort_keys=True, indent=4, separators=(',', ': ')))
        # ========== logstat end ==========
