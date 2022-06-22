# coding: utf-8

import os
import sys
import importlib
import json
import logging
import time

from collections import deque
from copy import deepcopy
from inspect import isgenerator
from urllib.parse import urlparse, urljoin

import pycurl
from pycurl_session import Session
from pycurl_session.response import Response
from pycurl_session.spider import settings
from pycurl_session.spider.exceptions import IgnoreRequest, DropItem, CloseSpider, PerformError, RetryRequest
from pycurl_session.spider.middleware import Statistics, RobotsTxt, Cookies
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
        self.session.set_timeout(self.settings["DOWNLOAD_TIMEOUT"])
        if self.settings["COOKIES_STORE_ENABLED"] and self.settings["COOKIES_STORE_DB"]:
            self.session.set_cookie_db(self.settings["COOKIES_STORE_DB"])

        self.multi_cookiejar = {}
        self.set_multi_cookiejar(self.settings["BOT"])

        self.cm = pycurl.CurlMulti()
        self.queue_pending = deque()
        self.queue_delay = deque()
        self.curl_handles = {}
        self.num_handles = 0    # running handle count

        self.spider_instance = {}
        self.spider_task = {}
        self.middleware = []
        self.pipeline = []

        self.robotstxt = RobotsTxt()
        self.set_middleware()
        self.set_pipeline()

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
        if "DEFAULT_REQUEST_HEADERS" in custom_settings:
            for k, v in custom_settings["DEFAULT_REQUEST_HEADERS"].items():
                headers.update({k.lower(): v})
        if (
            "USER_AGENT" in custom_settings
            and headers["user-agent"] == settings.USER_AGENT
        ):
            headers["user-agent"] = custom_settings["USER_AGENT"]
        self.settings["DEFAULT_HEADERS"] = headers

    def set_logger(self, name):
        logger = logging.getLogger(name)
        if len(logger.handlers) == 0:
            formatter = logging.Formatter(
                self.settings["LOG_FORMAT"], datefmt="%Y-%m-%d %H:%M:%S",
            )
            logger.setLevel(logging.DEBUG)
            ch = logging.StreamHandler()
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
        self.middleware.append(Cookies())
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
            if len(self.spider_task) == 0:
                break
            if spider_id in self.spider_task:
                item = self.spider_task[spider_id].get()
                if item is None:
                    self.spider_task.pop(spider_id)
                elif isinstance(item, TaskItem):
                    yield item

    def make_curl_handle(self, request, spider):
        url = request.url
        url_parsed = urlparse(url)
        url_domain = url_parsed.netloc
        top_domain = (
            url_domain[url_domain.find(".") :]
            if len(url_domain.split(".")) >= 2
            else url_domain
        )
        if top_domain not in self.curl_handles:
            self.curl_handles.update({top_domain: {"handles": [], "last": 0}})
        args = request.args
        if "method" not in args:
            method = "GET"
            args.update({"method": method})
        else:
            method = args["method"]
        request.method = method
        if "cookiejar" in request.meta:
            args["session_id"] = request.meta["cookiejar"]
            self.set_multi_cookiejar(request.meta["cookiejar"])
        c = self.session.prepare_curl_handle(url=url, **args)
        c.meta = request.meta
        c.top_domain = top_domain
        c.spider_id = spider.spider_id
        request.cookies = c.request["cookies"]
        c.spider_request = request
        return c

    def run_request_callback(self, request, response, spider):
        ret = request._run_callback(response)
        new_request = None
        try:
            if isgenerator(ret):
                new_request = next(ret)
                if isinstance(new_request, Request):
                    args = new_request.args
                    if "headers" not in args:
                        new_request.args.update({"headers": {}})
                    if "referer" not in new_request.args['headers']:
                        new_request.args['headers'].update({
                            "referer": response.request["url"]
                        })
                if isinstance(new_request, dict):
                    self.run_pipeline(new_request, spider)
        except StopIteration:
            pass
        except CloseSpider:
            self.manual_close_task(spider)
        finally:
            return ret, new_request

    def collect_curl_multi(self):
        if len(self.queue_pending) == 0:
            # init self.queue_pending
            try:
                queue_item = next(self.get_queue_item())
                if queue_item:
                    self.queue_pending.append(queue_item)
            except StopIteration:
                pass
        self.queue_delay.clear()
        while len(self.queue_pending) > 0:
            if self.num_handles >= self.settings["CONCURRENT_REQUESTS"]:
                break
            queue_item = self.queue_pending.popleft()
            spider_id, item = queue_item.spider_id, queue_item.item
            spider = self.spider_instance[spider_id]
            if isgenerator(item):
                # ========== process isgenerator start ==========
                try:
                    result = next(item)
                    if isinstance(result, Request):
                        self.queue_pending.append(TaskItem(spider_id, result))
                    self.queue_delay.append(TaskItem(spider_id, item))
                    if isinstance(result, dict):
                        self.run_pipeline(result, spider)
                except StopIteration:
                    continue
                except CloseSpider:
                    self.manual_close_task(spider)
                except Exception as e:
                    self.logger.exception(e)
                    continue
                # ========== process isgenerator end ==========
            elif isinstance(item, Request):
                # ========== process request start ==========
                url = item.url
                url_parsed = urlparse(url)
                url_domain = url_parsed.netloc
                top_domain = (
                    url_domain[url_domain.find(".") :]
                    if len(url_domain.split(".")) >= 2
                    else url_domain
                )
                if top_domain not in self.curl_handles:
                    self.curl_handles.update(
                        {top_domain: {"handles": [], "last": 0}}
                    )
                # ========== RobotsTxt start ==========
                if self.settings["ROBOTSTXT_OBEY"]:
                    try:
                        ret = self.robotstxt.process_request(item, spider)
                        if isinstance(ret, Request):
                            self.queue_delay.append(TaskItem(spider_id, item))
                            self.queue_delay.append(TaskItem(spider_id, ret))
                            continue
                        if isinstance(ret, Response):
                            self.queue_delay.append(TaskItem(spider_id, item))
                            continue
                    except IgnoreRequest:
                        del queue_item
                        continue
                # ========== RobotsTxt end ==========
                if (
                    time.time() - self.curl_handles[top_domain]["last"]
                    > self.settings["DOWNLOAD_DELAY"]
                ):
                    # add data to Request, e.g. cookies
                    c = self.make_curl_handle(item, spider)

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
                                    ret, new_request = self.run_request_callback(c.spider_request, ret, spider)
                                    if ret:
                                        self.queue_delay.append(TaskItem(spider_id, ret))
                                    if new_request:
                                        self.queue_delay.append(TaskItem(spider_id, new_request))
                                    get_new_queue_item = True
                                    break
                            except IgnoreRequest:
                                get_new_queue_item = True
                                del queue_item
                                break
                            except Exception as e:
                                spider._get_logger().exception(e)

                    if get_new_queue_item: continue
                    # ========== Middleware end ==========
                    self.cm.add_handle(c)
                    self.curl_handles[c.top_domain]["handles"].append(c)
                    self.curl_handles[c.top_domain]["last"] = time.time()
                    self.num_handles += 1
                    del queue_item
                else:
                    self.queue_delay.append(queue_item)
                # ========== process request end ==========

            # get more TaskItem, if all item put to curl or queue_delay
            if (len(self.queue_pending) == 0
                and self.num_handles < self.settings["CONCURRENT_REQUESTS"]
                # and len(self.queue_delay) == 0
            ):
                try:
                    queue_item = next(self.get_queue_item())
                    if queue_item:
                        self.queue_pending.append(queue_item)
                except StopIteration:
                    pass

        # put back to queue_pending
        while len(self.queue_delay) > 0:
            self.queue_pending.appendleft(self.queue_delay.pop())

    def process_response(self, response, c):
        spider_id = c.spider_id
        spider = self.spider_instance[spider_id]
        perform_time = c.getinfo(pycurl.TOTAL_TIME)
        if response.status_code in [301, 302] and (
            (
                "dont_redirect" not in response.meta
                and self.settings["REDIRECT_ENABLED"] == True
            )
            or (
                "dont_redirect" in response.meta
                and response.meta["dont_redirect"] != True
            )
        ):
            self.session._response_redirect(c, logger_handle=self.logger)
            self.cm.add_handle(c)
            self.curl_handles[c.top_domain]["handles"].append(c)
            self.curl_handles[c.top_domain]["last"] = time.time()
            self.num_handles += 1
            return
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
            c = self.session._response_retry(
                c,
                max_time=self.settings["RETRY_TIMES"],
                logger_handle=self.logger,
            )
            if c.retry < self.settings["RETRY_TIMES"]:
                self.cm.add_handle(c)
                self.curl_handles[c.top_domain]["handles"].append(c)
                self.curl_handles[c.top_domain]["last"] = time.time()
                self.num_handles += 1
            else:
                self.session._response_retry(
                    c,
                    max_time=self.settings["RETRY_TIMES"],
                    logger_handle=self.logger,
                )
                c.close()
            return
        try:
            ret, new_request = self.run_request_callback(c.spider_request, response, spider)
            if ret:
                self.queue_pending.append(TaskItem(spider_id, ret))
            if new_request:
                self.queue_pending.append(TaskItem(spider_id, new_request))
        except CloseSpider:
            self.manual_close_task(spider)
        except Exception as e:
            spider._get_logger().exception(e)
        c.close()
        return

    def process_curl_multi_ok(self, c):
        spider_id = c.spider_id
        spider = self.spider_instance[spider_id]

        self.cm.remove_handle(c)
        if c in self.curl_handles[c.top_domain]["handles"]:
            self.curl_handles[c.top_domain]["handles"].remove(c)
            self.curl_handles[c.top_domain]["last"] = time.time() # todo

        response = self.session.gather_response(c)
        response.meta = c.meta
        response.headers = c.response_headers

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
                        self.queue_pending.append(TaskItem(spider_id, ret))
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
            c.close()
            return
        # ========== Middleware end ==========
        # ========== process_response start ==========
        self.process_response(response, c)
        # ========== process_response end ==========

    def process_curl_multi_err(self, c, errno, errmsg):
        spider_id = c.spider_id
        spider = self.spider_instance[spider_id]

        self.cm.remove_handle(c)
        self.curl_handles[c.top_domain]["handles"].remove(c)
        # ========== Middleware start ==========
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
                        self.queue_pending.append(TaskItem(spider_id, ret))
                        get_new_queue_item = True
                        break
                    if isinstance(ret, Response):
                        self.process_response(ret, c)
                        break
                except RetryRequest:
                    c.retry += 1
                    if c.retry < self.settings["RETRY_TIMES"]:
                        self.cm.add_handle(c)
                        self.curl_handles[c.top_domain]["handles"].append(c)
                        self.curl_handles[c.top_domain]["last"] = time.time()
                        self.num_handles += 1
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
            c.close()
            return
        # ========== Middleware end ==========

    def manual_close_task(self, spider):
        spider_id = spider.spider_id
        spider.log("{} raise CloseSpider(). No more request will be add to queue.".format(spider_id))
        if spider_id in self.spider_task:
            self.spider_task.pop(spider_id)

    def process_close_call(self):
        # running_spider = [queue_item[0] for queue_item in self.queue_pending]
        # running_spider.extend([c.spider_id for domain, handles in self.curl_handles.items() for c in handles["handles"]])
        for spider_id, spider in self.spider_instance.items():
            # if spider_id in running_spider: continue
            # clean spider_task
            # if spider_id in self.spider_task:
            #     if self.spider_task[spider_id].count <= 0:
            #         self.spider_task.pop(spider_id)
            
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
                reason = "done"
                try:
                    spider.closed(reason)
                except Exception as e:
                    spider._get_logger().exception(e)


    def run(self):
        if not self.init_success: return
        # ========== schedule info start ==========
        self.logger.info("Schedule started")
        self.logger.info("Overridden settings: {0}".format(self.settings))
        self.logger.info("Enabled spider: {0}".format(list(self.spider_task.keys())))
        self.logger.info("Spider started")
        # ========== schedule info end ==========
        # ========== main loop start ==========
        loop_init = True
        while loop_init or self.num_handles > 0 or len(self.queue_pending) > 0:
            loop_init = False
            to_collect = False

            while 1:
                ret, self.num_handles = self.cm.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM:
                    break
            self.cm.select(0.001)
            num_q, ok_list, err_list = self.cm.info_read()
            for c in ok_list:
                self.process_curl_multi_ok(c)
                to_collect = True

            for c, errno, errmsg in err_list:
                self.process_curl_multi_err(c, errno, errmsg)
                to_collect = True

            if self.num_handles == 0 or to_collect:
                # update self.cm
                self.collect_curl_multi()
        # ========== main loop end ==========

        # all spider done, spider call closed() and item pipeline call close_spider()
        self.process_close_call()

        # ========== logstat start ==========
        if self.settings["ROBOTSTXT_OBEY"]:
            self.logstat.update(self.robotstxt.process_logstat())
        for middleware in self.middleware:
            if hasattr(middleware, "process_logstat"):
                self.logstat.update(middleware.process_logstat())
        self.logger.info("Dumping logstat:\n" + json.dumps(self.logstat, sort_keys=True, indent=4, separators=(',', ': ')))
        # ========== logstat end ==========
