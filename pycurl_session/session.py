# -*- coding: UTF-8 -*-

import os
import sys
import pycurl
import certifi
import json as m_json
import time
import tempfile
import uuid
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse, urlencode, urljoin, unquote, quote
from urllib.parse import ParseResult, urlunparse
from pycurl_session.cache import CacheDB
from pycurl_session.response import Response
from pycurl_session.auth import HTTPAUTH, HTTPAUTH_BASIC

import logging

logger = logging.getLogger("pycurl_session")


class HeaderHandle(object):
    def __init__(self, c) -> None:
        self.c = c

    def write(self, header_line):
        header_line = header_line.decode("iso-8859-1")
        if ":" in header_line:
            self.c.response_headers.append(header_line.strip())

    def clear(self):
        self.c.response_headers.clear()

class Session(object):
    def __init__(self, session_id=None, store_cookie=True):
        if session_id:
            self.session_id = session_id
            self.save_session = True
        else:
            self.session_id = str(uuid.uuid4())
            self.save_session = False
        if store_cookie:
            temp_dir = tempfile.gettempdir()
            path = os.path.join(temp_dir, "pycurl_session")
            if not os.path.exists(path):
                os.makedirs(path)
            self.cookie_db_path = os.path.join(path, "cookies.db")
        else:
            self.cookie_db_path = ":memory:"
        self.cookie_db = CacheDB(self.cookie_db_path)

        self.c = pycurl.Curl()
        self.auth = {}
        self.proxy = {}

        self.headers = {}
        self.useragent = ""
        # self.response_headers = []
        self.history = []
        self._max_retry_times = 3
        self._retry_interval = 5
        self._backoff = [self._retry_interval]
        self.retry_http_codes = [500, 502, 503, 504, 522, 524, 408, 429]
        self.redirect_http_codes = [301, 302, 303, 307, 308]
        self._timeout = 30

        self._fh = None
        self._ssl_cipher_list = None # "ALL:!EXPORT:!EXPORT40:!EXPORT56:!aNULL:!LOW:!RC4:@STRENGTH"
        self.version_info = pycurl.version_info()
        self._verify = True

    def set_cookie_db(self, cookie_db_path):
        dir_path = os.path.dirname(cookie_db_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        self.cookie_db_path = cookie_db_path
        self.cookie_db = CacheDB(self.cookie_db_path)

    def set_logger(self, log_path=None):
        if log_path:
            dir_path = os.path.dirname(log_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            logger.removeHandler(self._fh)
            self._fh = logging.FileHandler(filename=log_path)
            self._fh.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)-5s [%(module)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            self._fh.setFormatter(formatter)
            logger.addHandler(self._fh)

    def get(self, url, **args):
        return self.request("GET", url=url, **args)

    def post(self, url, **args):
        return self.request("POST", url=url, **args)

    def put(self, url, **args):
        return self.request("PUT", url=url, **args)

    def patch(self, url, **args):
        return self.request("PATCH", url=url, **args)

    def options(self, url, **args):
        return self.request("OPTIONS", url=url, **args)

    def head(self, url, **args):
        return self.request("HEAD", url=url, **args)

    def delete(self, url, **args):
        return self.request("DELETE", url=url, **args)

    def request(self, method, url, **args):
        c = self.c
        if "c" in args:
            if isinstance(args["c"], pycurl.Curl):
                c = args["c"]
            args.pop("c")
        c = self.prepare_curl_handle(method, url=url, c=c, **args)
        return self.send(c)

    def send(self, c):
        response = Response()
        while True:
            if c.retry > c.max_retry_times:
                break
            try:
                c.perform()
                response = self.gather_response(c)
                if response.status_code in self.redirect_http_codes and c.allow_redirects:
                    self._response_redirect(c, response.status_code, logger_handle=logger)
                    continue
                logger.info(
                    "({0}) <{1} {2} {3}s> (referer: {4})".format(
                        response.status_code,
                        c.request["method"],
                        c.request["url"],
                        c.getinfo(pycurl.TOTAL_TIME),
                        c.request["referer"],
                    )
                )
                if response.status_code in self.retry_http_codes:
                    self._response_retry(c, logger_handle=logger)
                    continue
                break
            except pycurl.error as e:
                # timeout or raise error
                # 28 - OPERATION_TIMEDOUT
                # 12 - FTP_ACCEPT_TIMEOUT
                code, msg = e.args
                if code in [12, 28] and c.retry < c.max_retry_times:
                    logger.error(msg)
                else:
                    raise
                c.retry += 1
                if c.retry <= c.max_retry_times:
                    logger.info("Retry [{0}] {1}".format(c.retry, c.request["url"]))
                    c.header_handle.clear()
                    c.response_headers.clear()
                    c.buffer.seek(0)
                    c.buffer.truncate()
            except Exception as e:
                logger.error(e, stack_info=True)
                raise
        return response

    def init_curl_var(self, c):
        if hasattr(c, "request"):
            c.request.clear()
        else:
            c.request = {}
        if hasattr(c, "header_handle"):
            c.header_handle.clear()
        else:
            c.header_handle = HeaderHandle(c)
        if hasattr(c, "response_headers"):
            c.response_headers.clear()
        else:
            c.response_headers = []
        if hasattr(c, "buffer"):
            c.buffer.seek(0)
            c.buffer.truncate()
        else:
            c.buffer = BytesIO()
        if not hasattr(c, "retry"): c.retry = 0
        if not hasattr(c, "max_retry_times"): c.max_retry_times = self._max_retry_times
        if not hasattr(c, "allow_redirects"): c.allow_redirects = True
        if not hasattr(c, "proxy"): c.proxy = ""
        if not hasattr(c, "cert"): c.cert = ""
        if not hasattr(c, "verify"): c.verify = True
        # for spider
        # if hasattr(c, "spider_request"): c.spider_request = None


    def reconstruct_url(self, url_info, params=None, quote_safe=""):
        netloc = url_info.netloc
        scheme = url_info.scheme.lower()

        if url_info.username:
            netloc = netloc.split("@")[-1]

        query = url_info.query if url_info.query else ""
        if params:
            if isinstance(params, dict):
                params = "&".join(["{0}={1}".format(k, v) for k, v in params.items()])
            query = query + "&" + params if query else params
        if query:
            _tmp = []
            for pair in query.split("&"):
                kv = pair.split("=", 1)
                if len(kv) == 2:
                    _tmp.append(tuple(kv))
                else:
                    _tmp.append((kv, ""))
            query = urlencode(_tmp, safe=quote_safe)
        return urlunparse(ParseResult(
            scheme,
            netloc,
            quote(unquote(url_info.path)),
            quote(unquote(url_info.params), safe="=;,"),    # rfc3986 3.3. Path
            query,
            quote(unquote(url_info.fragment))
        ))


    def prepare_curl_handle(
        # fmt: off
        self, method, url, c=None,
        headers=None, cookies=None, auth=None, proxy=None, cert=None,
        params=None, data=None, json=None, files=None, multipart=False,
        timeout=None, allow_redirects=True,
        hooks=None, stream=None, verify=True, verbose=False, quote_safe="",
        session_id=None
        # fmt: on
    ):
        ''' c (curl):
                request: dict
                    cookies: dict
                    method: str
                    url: str
                    headers: dict
                    referer: str
                header_handle: HeaderHandle
                response_headers: list
                buffer: BytesIO
                retry: int
                max_retry_times: int
                allow_redirects: bool
                proxy: str
                cert: str
                verify: bool
        '''
        if c is None:
            c = pycurl.Curl()
        self.init_curl_var(c)
        c.session_id = session_id if session_id else None

        self._set_proxy(c, proxy)
        self._set_verbose(c, verbose)

        # common setting
        c.allow_redirects = allow_redirects
        c.setopt(c.FOLLOWLOCATION, 0)
        if not timeout:
            timeout = self._timeout
        c.setopt(c.CONNECTTIMEOUT, timeout)
        c.setopt(c.TIMEOUT, timeout)
        # c.setopt(c.HEADER,1)    # write header + body
        c.setopt(c.MAXREDIRS, 5)
        c.setopt(c.ENCODING, "")    # Important
        # c.setopt(c.ENCODING, "gzip,deflate")
        # c.setopt(c.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_2)
        c.setopt(c.HEADERFUNCTION, c.header_handle.write)
        c.setopt(c.WRITEDATA, c.buffer)

        # if len(self.history) > 0 and request_referer == None:
        #     request_referer = self.history[-1]
        #     c.setopt(c.REFERER, self.history[-1])
        # if request_referer:
        #     c.setopt(c.REFERER, request_referer)
        # c.request.update({"referer": request_referer})

        # reconstruct url
        url_info = urlparse(url)
        domain = url_info.hostname

        url = self.reconstruct_url(url_info, params, quote_safe=quote_safe)
        c.request.update({"url": url})
        c.setopt(c.URL, url)

        if url_info.scheme.lower() == "https":
            self._set_ssl(c)

        # parse headers before check auth
        request_headers = self._prepare_request_headers(c, headers, url)
        # check BASIC AUTH. Url first
        if url_info.username:
            auth = HTTPAUTH_BASIC(url_info.username, url_info.password)
        if isinstance(auth, HTTPAUTH):
            auth.attach(c, url, request_headers)
            self.auth.update({domain: auth})
        elif domain in self.auth:
            self.auth[domain].attach(c, url, request_headers)

        # priority from low to high: cache -> session -> header -> params
        # request_headers include cookie in header and session
        new_cookies = self.get_cookies(url, c.session_id)
        if "cookie" in request_headers:
            cookies_in_header_str = request_headers.pop("cookie")
            for item in cookies_in_header_str.split(";"):
                kv = item.strip().split("=")
                if len(kv) == 2:
                    new_cookies.update({kv[0]: kv[1]})
        if cookies:
            if isinstance(cookies, dict):
                new_cookies.update(cookies)
            elif isinstance(cookies, str):
                for item in cookies.split(";"):
                    kv = item.strip().split("=")
                    if len(kv) == 2:
                        new_cookies.update({kv[0]: kv[1]})
            elif isinstance(cookies, list):
                for kv in cookies:
                    if len(kv) == 2:
                        new_cookies.update({"{0}".format(kv[0]): "{0}".format(kv[1])})
        c.request.update({"cookies": new_cookies})
        if new_cookies:
            # both work, but header first
            cookie_str = "; ".join(["{0}={1}".format(k, v) for k, v in new_cookies.items()])
            request_headers.update({"cookie": cookie_str})
            c.setopt(pycurl.COOKIE, cookie_str)

        ## data send
        # for post:
        #   1. data
        #       accept one of:
        #           a. {field: str}
        #           b. raw_str
        #   2. multipart + data
        #       accept one of:
        #           a. {field: str, field: @path, field: [@path, ...]}
        #           b. [(field, str), (field, @path), (field, [@path, ...])]
        #   3. files + data(option)
        #       files accept {field: path} or {field: path_list}
        #       data like 2
        #   4. json_data
        #       will add or change "content-type" to "application/json" in header if not 'json' in content-type
        #       accept one of:
        #           a. @path            - string, for post one file
        #           b. {field: str}
        #           c. raw_str
        # for put or patch:
        #   a. will add "content-type" to "application/json" in header if no content-type in header
        #   b. files > json_data > data, only one will use
        #       files only accept "@path" for one file
        #       json_data and data accept dict or raw_str, note: "@path" is string here
        # for get:
        #   params accept dict or raw_str
        json_data = json
        method = method.upper()
        c.request.update({"method": method})
        if method == "POST":
            c.setopt(c.POST, 1)
            if multipart or files is not None:
                # Multipart/form-data
                post_data = []
                if isinstance(data, dict):
                    for field, item in data.items():
                        if isinstance(item, list):
                            for s in item:
                                if s.startswith("@"):
                                    if not os.path.exists(s[1:]):
                                        pass  # warning
                                    post_data.append((field, (c.FORM_FILE, s[1:])))
                                else:
                                    post_data.append((field, s))
                        else:
                            if item.startswith("@"):
                                if not os.path.exists(item[1:]):
                                    pass  # warning
                                post_data.append((field, (c.FORM_FILE, item[1:])))
                            else:
                                post_data.append((field, item))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, tuple) and len(item) == 2:
                            field = item[0]
                            s = item[1]
                            if s.startswith("@"):
                                if not os.path.exists(s[1:]):
                                    pass  # warning
                                post_data.append((field, (c.FORM_FILE, s[1:])))
                            else:
                                post_data.append((field, s))
                if files:
                    if isinstance(files, dict):
                        for field, item in files.items():
                            if isinstance(item, list):
                                for s in item:
                                    if not os.path.exists(s):
                                        pass  # warning
                                    post_data.append((field, (c.FORM_FILE, s)))
                            else:
                                post_data.append((field, (c.FORM_FILE, item)))
                    else:
                        logger.error("params[files] need like {'field':path_to_file}")
                if post_data:
                    c.setopt(c.HTTPPOST, post_data)
            elif data is None and files is None and json_data is not None:
                # application/json
                if (
                    "content-type" in request_headers
                    and "json" not in request_headers["content-type"]
                ):
                    # remove content-type, if not json type
                    request_headers.pop("content-type")
                if "content-type" not in request_headers:
                    request_headers.update({"content-type": "application/json"})
                if (
                    isinstance(json_data, str)
                    and len(json_data) > 1
                    and json_data.startswith("@")
                ):
                    json_file = json_data[1:]
                    if os.path.exists(json_file):
                        with open(json_file) as f:
                            json_data = m_json.loads(f.read())
                    else:
                        # warning
                        json_data = {}
                json_body = (
                    m_json.dumps(json_data) if isinstance(json_data, dict) else json_data
                )
                c.setopt(c.POSTFIELDS, json_body)
            elif data is not None:
                # application/x-www-form-urlencoded
                if "content-type" not in request_headers:
                    request_headers.update({"content-type": "application/x-www-form-urlencoded"})
                post_data = urlencode(data) if isinstance(data, dict) else data
                c.setopt(c.POSTFIELDS, post_data)
            else:
                c.setopt(c.POSTFIELDS, "")
        elif method == "PUT" or method == "PATCH":
            c.setopt(c.CUSTOMREQUEST, method)
            # application/json
            if "content-type" not in request_headers:
                request_headers.update({"content-type": "application/json"})
            # files > json_data > data, only one will use
            if files is not None and isinstance(files, str):
                with open(files) as f:
                    data_body = f.read()
                c.setopt(c.POSTFIELDS, data_body)
            elif json_data is not None:
                data_body = (
                    m_json.dumps(json_data) if isinstance(json_data, dict) else json_data
                )
                c.setopt(c.POSTFIELDS, data_body)
            else:
                data_body = m_json.dumps(data) if isinstance(data, dict) else data
                c.setopt(c.POSTFIELDS, data_body)
        elif method == "GET":
            c.setopt(c.HTTPGET, 1)
        elif method == "HEAD":
            c.setopt(c.NOBODY, 1)
        else:
            c.setopt(c.CUSTOMREQUEST, method)

        c.request.update({"headers": request_headers})
        headers_list = ["{0}: {1}".format("-".join(x.capitalize() for x in k.split("-")), v) for k, v in request_headers.items()]
        c.setopt(c.HTTPHEADER, headers_list)
        return c

    def gather_response(self, c):
        response = Response(session=self)
        response.status_code = c.getinfo(pycurl.RESPONSE_CODE)
        response.headers = c.response_headers
        response.content = c.buffer
        response.url = c.getinfo(pycurl.EFFECTIVE_URL)
        # self.history.append(response.url)
        response.request.update(
            {
                "url": c.request["url"],
                "cookies": c.request["cookies"],
                "headers": c.request["headers"],
            }
        )
        self._response_decode(response)  # guess response.text
        self.save_cookies(response, c.session_id)
        return response

    def _set_ssl(self, c):
        if c.cert:
            c.setopt(c.CAINFO, c.cert)
        else:
            c.setopt(c.CAINFO, certifi.where())
        if c.verify and self._verify:
            c.setopt(c.SSL_VERIFYPEER, 1)
            c.setopt(c.SSL_VERIFYHOST, 2)
        else:
            c.setopt(c.SSL_VERIFYPEER, 0)
            c.setopt(c.SSL_VERIFYHOST, 0)
        if self._ssl_cipher_list:
            c.setopt(c.SSL_CIPHER_LIST, self._ssl_cipher_list)


    def _prepare_request_headers(self, c, headers, url):
        url_info = urlparse(url)
        domain = url_info.hostname

        request_headers = self.headers.copy()
        request_headers = {key.lower().strip(): val for key, val in request_headers.items()}
        request_headers.update({"host": domain})

        request_referer = None
        if headers and isinstance(headers, dict):
            for k, v in headers.items():
                if k.lower() == "cookie":
                    if "cookie" not in request_headers:
                        request_headers.update({"cookie": ""})
                    request_headers["cookie"] = request_headers["cookie"] + "; " + v
                    continue
                request_headers.update({k.lower(): v})
                if k.lower() == "referer":
                    request_referer = v
                # if k.lower() == "user-agent":
                #     c.setopt(c.USERAGENT,v)
                #     self.useragent = v
        elif headers and isinstance(headers, list):
            for s in headers:
                t = s.split(":", 1)
                if len(t) == 2:
                    if t[0].lower() == "cookie":
                        if "cookie" not in request_headers:
                            request_headers.update({"cookie": ""})
                        request_headers["cookie"] = request_headers["cookie"] + "; " + t[1]
                        continue
                    request_headers.update({t[0].lower(): t[1]})
                    if t[0].lower() == "referer":
                        request_referer = t[1]
                    # if t[0].lower() == "user-agent":
                    #     c.setopt(c.USERAGENT,t[1])
                    #     self.useragent = v
        if request_referer != "" and request_referer is not None:
            c.setopt(c.REFERER, request_referer)
            c.request.update({"referer": request_referer})
        else:
            c.request.update({"referer": None})
        return request_headers

    def _response_redirect(self, c, status_code, logger_handle=None):
        origin_url = c.request["url"]
        origin_method = c.request["method"].upper()

        for header in c.response_headers:
            if "location:" in header.lower():
                url = header.split(":", 1)[1].strip()
                url = urljoin(origin_url, url)
                url_info = urlparse(url)
                # reset url
                url = self.reconstruct_url(url_info)
                c.request.update({"url": url})
                c.setopt(c.URL, url)
                if url_info.scheme.lower() == "https":
                    self._set_ssl(c)

                domain = url_info.hostname
                c.request["headers"].update({"host": domain})
                request_headers = c.request["headers"]
                # reset auth, if need
                origin_url_info = urlparse(origin_url)
                origin_domain = origin_url_info.hostname
                if domain != origin_domain:
                    if domain in self.auth:
                        self.auth[domain].attach(c, url, request_headers)
                    else:
                        if url_info.username:
                            auth = HTTPAUTH_BASIC(url_info.username, url_info.password)
                            auth.attach(c, url, request_headers)
                            self.auth.update({domain: auth})
                # reset cookie
                new_cookies = self.get_cookies(url, c.session_id)
                if "cookie" in request_headers and origin_domain in domain:
                    # when two domain is same or new domain is subdomain
                    # add/update cookie in origin header
                    # NOTE: not exactly correct
                    cookies_in_header_str = request_headers.pop("cookie")
                    for item in cookies_in_header_str.split(";"):
                        kv = item.strip().split("=")
                        if len(kv) == 2:
                            new_cookies.update({kv[0]: kv[1]})
                c.request.update({"cookies": new_cookies})
                if new_cookies:
                    # both work, but header first
                    cookie_str = "; ".join(["{0}={1}".format(k, v) for k, v in new_cookies.items()])
                    request_headers.update({"cookie": cookie_str})
                    c.setopt(pycurl.COOKIE, cookie_str)
                # reset header
                c.request.update({"headers": request_headers})
                headers_list = ["{0}: {1}".format("-".join(x.capitalize() for x in k.split("-")), v) for k, v in request_headers.items()]
                c.setopt(c.HTTPHEADER, headers_list)
                break
        # update curl
        c.setopt(c.REFERER, origin_url)
        # for 3xx, update method
        # referer: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Location
        #   303 - all change to GET
        #   307 & 308 - all do not change
        #   301 & 302 - most of the time do not change?
        # referer: https://fetch.spec.whatwg.org/#http-redirect-fetch
        #   one of the following is true, change to GET (except HEAD)
        #       - 301/302 and method=POST
        #       - 303 and method is not GET or HEAD
        method = origin_method
        if (status_code == 303 and method != "HEAD") or (status_code in [301, 302] and method == "POST"):
            method = "GET"
        if method == "POST":
            c.setopt(c.POST, 1)
        elif method == "GET":
            c.setopt(c.HTTPGET, 1)
        elif method == "HEAD":
            c.setopt(c.NOBODY, 1)
        else:
            # put, patch, and other method
            c.setopt(c.CUSTOMREQUEST, method)
        c.buffer.seek(0)
        c.buffer.truncate()
        c.header_handle.clear()
        c.response_headers.clear()

        if logger_handle:
            status_code = c.getinfo(pycurl.RESPONSE_CODE)
            perform_time = c.getinfo(pycurl.TOTAL_TIME)
            logger_handle.info(
                "({0}) to <Redirect {1}> from <{2} {3} {4}s> (referer: {5})".format(
                    status_code,
                    c.request["url"],
                    origin_method,
                    origin_url,
                    perform_time,
                    c.request["referer"],
                )
            )

    def _response_retry(self, c, logger_handle=None):
        c.retry += 1
        if c.retry >= len(self._backoff):
            sleep_time = self._backoff[-1]
        else:
            sleep_time = self._backoff[(c.retry - 1) % len(self._backoff)]
        if c.retry <= c.max_retry_times:
            if logger_handle:
                logger_handle.info(
                    "Retry #{0} [after {1}s] {2}".format(
                        c.retry,
                        sleep_time,
                        c.request["url"],
                    )
                )
            c.buffer.seek(0)
            c.buffer.truncate()
            c.header_handle.clear()
            c.response_headers.clear()
            time.sleep(sleep_time)
        else:
            if logger_handle:
                if c.max_retry_times > 0:
                    logger_handle.info(
                        "Failed to process <{0} {1}>, try max time.".format(
                            c.request["method"],
                            c.request["url"]
                        )
                    )
                else:
                    logger_handle.info(
                        "Failed with no retry <{0} {1}>".format(
                            c.request["method"],
                            c.request["url"]
                        )
                    )

    def set_retry_times(self, times: int = 3, backoff: list = []):
        if times and int(times) > 0:
            self._max_retry_times = times
        if backoff and isinstance(backoff, list):
            self._backoff = [x for x in backoff if isinstance(x, (int, float))]

    def set_timeout(self, timeout: int = 60):
        if timeout and int(timeout) > 1:
            self._timeout = timeout

    def set_proxy(self, proxy):
        # proxy: None: use self.proxy, "": unset self.proxy, "xxx": set self.proxy
        if proxy == "":
            self.proxy = {}
        elif isinstance(proxy, str):
            url_info = urlparse(proxy)
            self.proxy.update(
                {
                    "scheme": url_info.scheme,
                    "hostname": url_info.hostname,
                    "port": url_info.port,
                    "username": url_info.username,
                    "password": url_info.password,
                }
            )

    def _set_proxy(self, c, proxy):
        c.proxy = proxy
        if proxy and isinstance(proxy, str):
            proxy_parsed = urlparse(proxy)
            proxy_info = {
                "scheme": proxy_parsed.scheme,
                "hostname": proxy_parsed.hostname,
                "port": proxy_parsed.port,
                "username": proxy_parsed.username,
                "password": proxy_parsed.password,
            }
        else:
            proxy_info = self.proxy
        if proxy_info:
            c.setopt(c.IPRESOLVE, pycurl.IPRESOLVE_V4)
            c.setopt(c.PROXY, proxy_info["hostname"])
            if proxy_info.get("scheme"):
                if proxy_info["scheme"].lower() == "socks5":
                    c.setopt(c.PROXYTYPE, pycurl.PROXYTYPE_SOCKS5)
                if proxy_info["scheme"].lower() == "socks5h":
                    c.setopt(c.PROXYTYPE, pycurl.PROXYTYPE_SOCKS5_HOSTNAME)
                elif proxy_info["scheme"].lower() == "socks4":
                    c.setopt(c.PROXYTYPE, pycurl.PROXYTYPE_SOCKS4)
                elif proxy_info["scheme"].lower() == "socks4a":
                    c.setopt(c.PROXYTYPE, pycurl.PROXYTYPE_SOCKS4A)
                # elif proxy_info["scheme"].lower() == "https":         # Added in 7.52.0 for OpenSSL, GnuTLS and NSS
                #     c.setopt(c.PROXYTYPE, pycurl.PROXYTYPE_HTTPS)
                else:
                    c.setopt(c.PROXYTYPE, pycurl.PROXYTYPE_HTTP)
            if proxy_info.get("port"):
                c.setopt(c.PROXYPORT, proxy_info["port"])
            if proxy_info.get("username") and proxy_info.get("password"):
                c.setopt(
                    pycurl.PROXYUSERPWD,
                    "{0}:{1}".format(proxy_info["username"], proxy_info["password"]),
                )

    def _set_verbose(self, c, verbose):
        if verbose:
            c.setopt(c.VERBOSE, 1)
        else:
            c.setopt(c.VERBOSE, 0)

    def _response_decode(self, response):
        content_type = ""
        charset = None
        charset_in_response = None
        charset_in_html = None
        for header in response.headers:
            if "content-type:" in header.lower():
                header_content = header.split(":")[1].lower()
                if ";" in header_content:
                    content_type = header_content.split(";")[0].strip()
                else:
                    content_type = header_content.strip()
                response.content_type = content_type
                for item in header_content.split(";"):
                    if "charset=" in item:
                        charset_in_response = item.replace("charset=", "").strip()
                        if "," in charset_in_response:
                            charset_in_response = charset_in_response.split(",")[0].strip()
        if "text" in content_type:
            response.text = response.content.getvalue()
            if len(response.text) > 0:
                charset_in_html = response.xpath("//head/meta[@charset]/@charset").get()
                if charset_in_html is None:
                    content = response.xpath(
                        "//head/meta[contains(@content, 'charset=')]/@content"
                    ).get()
                    if content:
                        for item in content.split(";"):
                            if "charset=" in item:
                                charset_in_html = item.replace("charset=", "").strip()
                                if "," in charset_in_html:
                                    charset_in_html = charset_in_html.split(",")[0].strip()

        charset_decode = False
        for charset in [charset_in_html, charset_in_response, "utf-8"]:
            try:
                if charset is None:
                    continue
                response.text = response.content.getvalue().decode(charset)
                response.encoding = charset
                charset_decode = True
                break
            except UnicodeDecodeError:
                continue
        if charset_decode == False:
            response.text = ""
            response.encoding = "unkown"

    def save_cookies(self, response, session_id=None):
        if not session_id:
            session_id = self.session_id
        response.cookies = {}
        params = []
        params_del = []
        for item in response.headers:
            header_name, header_value = item.split(":", 1)
            if header_name.lower() == "set-cookie":
                cookie_str = self.byte2str(header_value).strip()
                # print(cookie_str)
                cookie = cookie_str.split(";")
                name = ""
                value = ""
                domain = ""
                path = ""
                expires = ""
                for kv in cookie:
                    kv = kv.strip()
                    if kv.lower().startswith("path="):
                        path = kv.split("=")[1].strip()
                    elif kv.lower().startswith("domain="):
                        domain = kv.split("=")[1].strip()
                    elif kv.lower().startswith("expires="):
                        if expires:  # max-age already
                            continue
                        expires = kv.split("=")[1].strip()
                        expires_origin = expires
                        expires = expires.replace("-", " ").replace("+", "").strip()
                        if "," in expires:
                            expires = expires[expires.find(",") + 1 :].strip()
                        if "gmt" not in expires.lower():
                            # not endswith('GMT'), endswith('0000')
                            if len(expires.split(" ")[-1]) == 4:
                                expires = expires[: -4].strip()
                        else:
                            expires = expires.replace("gmt", "").replace("GMT", "").strip()
                        if len(expires.split(" ")[2]) == 2:
                            dt_format = "%d %b %y %H:%M:%S"
                        else:
                            dt_format = "%d %b %Y %H:%M:%S"
                        try:
                            dt = datetime.strptime(expires, dt_format)
                        except ValueError:
                            logger.warning("Cannot format cookie expires: {}".format(expires_origin))
                            expires = ""
                            continue
                        expires = int((dt - datetime(1970, 1, 1)).total_seconds())
                    elif kv.lower().startswith("max-age="):
                        expires = int(time.time()) + int(kv.split("=")[1].strip())
                    elif kv.lower().startswith("version="):
                        continue
                    else:
                        kv_split = kv.split("=", 1)
                        if len(kv_split) == 2 and cookie_str.startswith(kv_split[0]):
                            name = kv_split[0].strip()
                            value = kv_split[1].strip()
                if domain == "":
                    domain = urlparse(response.url).hostname
                params.append((session_id, name, value, domain, path, expires))
                if name not in response.cookies:
                    response.cookies.update({name: value})
                response.cookies.update({name: value})
                if value in ["delete"]:  # value = 'delete': delete this cookie
                    params_del.append((session_id, name, domain, path))

        if len(params):
            self.cookie_db.save_cookies(params)
        if len(params_del):
            self.cookie_db.delete_cookies(params_del)

    def get_cookies(self, request_url="", session_id=None):
        if not session_id:
            session_id = self.session_id
        return self.cookie_db.get_cookies(session_id, request_url)

    def clear_cookies(self, session_id=None):
        if not session_id:
            session_id = self.session_id
        self.cookie_db.clear_cookies(session_id)

    def unset_cookies(self, session_id=None, cookies=None):
        if not session_id:
            session_id = self.session_id
        cookies = cookies or []
        self.cookie_db.unset_cookies(session_id, cookies)

    def byte2str(self, data, encoding="utf-8"):
        if isinstance(data, bytes):
            return data.decode(encoding)
        return data

    def __del__(self):
        if self.save_session == False:
            self.cookie_db.clear_cookies(self.session_id)
