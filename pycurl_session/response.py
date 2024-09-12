# -*- coding: UTF-8 -*-

import os
import json
import re
from io import BytesIO
from lxml import etree
from urllib.parse import urlparse, urljoin, unquote, quote


class Response(object):
    def __init__(self, session=None):
        self.headers = []
        self.url = None
        self.status_code = None
        self.content = BytesIO()
        self.text = ""
        self.content_type = ""
        self.encoding = None
        self.cookies = {}
        self.request = {}
        self.meta = {}
        self.session = session

    def xpath(self, xpath):
        if self.text == "":
            return Selector([])
        html = etree.HTML(self.text)
        result = html.xpath(xpath) if html is not None else []
        return Selector(result)

    def css(self, css):
        if self.text == "":
            return Selector([])
        html = etree.HTML(self.text)
        result = html.cssselect(css)
        return Selector(result)

    def re(self, pattern, flags=re.I):
        if self.text == "":
            return Selector([])
        result = re.findall(pattern, self.text, flags=flags)
        return Selector(result)

    @property
    def title(self):
        return self.xpath("//head/title/text() | //body//title/text()").get("")

    @property
    def body(self):
        return self.text

    @property
    def status(self):
        return self.status_code

    def json(self):
        if self.text:
            try:
                result = json.loads(self.text)
                return result
            except Exception:
                raise
        else:
            return ""

    def urljoin(self, url):
        return urljoin(self.url, url)

    def unquote(self, url):
        return unquote(url)

    def json_loads(self, s):
        return json.loads(s)

    def submit_form(
        self,
        formid=None,
        formname="",
        formxpath="",
        formcss="",
        formnumber=1,
        method="POST",
        action=None,
        formdata=None,
        files=None,
        **args
    ):
        form = self._get_form(formid, formname, formxpath, formcss, formnumber)
        action = self._get_form_action(form, action)
        _inputs = form.xpath(".//input").getall()
        _form_data = self._get_form_inputs(form)
        if isinstance(formdata, dict):
            _form_data.update(formdata)
        if method.lower() == "get":
            query = "&".join(["{0}={1}".format(k, quote(unquote(v))) for k, v in _form_data.items()])
            if "?" in action:
                action = action + "&" + query
            else:
                action = action + "?" + query
            _form_data = None
        c = self.session.prepare_curl_handle(
            method=method,
            url=action,
            c=self.session.c,
            data=_form_data,
            files=files,
            **args
        )
        return self.session.send(c)

    def _get_form(self, formid=None, formname="", formxpath="", formcss="", formnumber=1):
        if formid:
            form = self.xpath("//form[@id='{0}']".format(formid)).get()
        elif formname:
            form = self.xpath("//form[@name='{0}']".format(formname)).get()
        elif formxpath:
            form = self.xpath(formxpath).get()
        elif formcss:
            form = self.css(formcss).get()
        else:
            if not formnumber: formnumber = 1
            if isinstance(formnumber, int) and formnumber < 1: formnumber = 1
            form = self.xpath("(//form)[{0}]".format(formnumber)).get()
        if form is None:
            raise Exception("form not found")
        form = Selector(ele=form)
        return form

    def _get_form_action(self, form, action):
        if action is None:
            action = form.xpath("./@action").get()
        action = self.urljoin(action)
        return action

    def _get_form_inputs(self, form):
        inputs = form.xpath(".//input").getall()
        form_data = {}
        for ele in inputs:
            ele = Selector(ele=ele)
            name = ele.xpath("./@name").get()
            if name:
                value = ele.xpath("./@value").get()
                form_data.update({name: value if value else ""})
        return form_data

    def get_header(self, item):
        value = ""
        if self.headers is None: return value
        for header in reversed(self.headers):
            if ":" not in header:
                continue
            key, val = header.split(":", 1)
            if key.lower() == item.lower():
                value = val.strip()
                break
        return value

    def save(self, path, encoding="utf-8"):
        dir_path_exists = True
        dir_path = os.path.dirname(path)
        if dir_path == "": dir_path = "./"
        if not os.path.exists(dir_path):
            dir_path_exists = False
        if self.content:
            self.content.seek(0)
        if self.content.getbuffer().nbytes > 0:
            if not dir_path_exists:
                os.makedirs(dir_path)
            with open(path, "wb") as f:
                f.write(self.content.getbuffer())
                return True
        elif self.text:
            if not dir_path_exists:
                os.makedirs(dir_path)
            enc = self.encoding if self.encoding else encoding
            with open(path, "w", encoding=enc) as f:
                f.write(self.text)
                return True
        return False


class Selector(object):
    def __init__(self, default=None, text="", ele=None):
        self.lst = []
        self.text = text
        self.ele = ele
        if text or ele is not None:
            self.type = "Selector"
        elif default is not None:
            if isinstance(default, list):
                for item in default:
                    if isinstance(item, Selector):
                        self.lst.append(item)
                    else:
                        self.lst.append(Selector(item))
                self.type = "SelectorList"
            elif isinstance(default, str):
                self.text = default
                self.type = "Selector"
            else:
                self.ele = default
                self.type = "Selector"

    def get(self, default=None):
        sel = (self.lst or [self])[0]
        if isinstance(sel, str): return sel
        elif isinstance(sel, Selector):
            if sel.text: return sel.text
            if sel.ele is not None: return sel.ele
        return default

    def getall(self):
        if len(self.lst) > 0:
            return [sel.get() for sel in self.lst]
        else:
            ele = self.get()
            return [ele] if ele else []

    def extract_first(self, default):
        return self.get(default=default)

    def extract(self):
        return self.getall()

    def __len__(self):
        if self.type == "Selector":
            return 1 if self.text or self.ele is not None else 0
        elif self.type == "SelectorList":
            return len(self.lst)
        return 0

    def __iter__(self):
        self.i = 0
        self.max = len(self)
        return self

    def __next__(self):
        if self.i < self.max:
            if self.type == "Selector" and self.text:
                item = self.text
            elif self.type == "Selector" and self.ele is not None:
                item = self.ele
            elif self.type == "SelectorList":
                item = self.lst[self.i]
            self.i += 1
            return item
        raise StopIteration

    def __getitem__(self, index):
        return self.getall()[index]

    def xpath(self, xpath):
        if self.type == "Selector":
            if self.ele is not None:
                html = self.ele
            elif self.text:
                html = etree.HTML(self.text)
            else:
                raise Exception("text is empty")
            result = html.xpath(xpath)
            return Selector(result)
        elif self.type == "SelectorList":
            ret = []
            for sel in self.lst:
                ret_sel = sel.xpath(xpath)
                if ret_sel.type == "SelectorList":
                    ret.extend(ret_sel.getall())
                else:
                    ret.append(ret_sel)
            return Selector(ret)

    def css(self, css):
        if self.type == "Selector":
            if self.ele is not None:
                html = self.ele
            elif self.text:
                html = etree.HTML(self.text)
            else:
                raise Exception("text is empty")
            result = html.cssselect(css)
            return Selector(result)
        elif self.type == "SelectorList":
            ret = []
            for sel in self.lst:
                ret_sel = sel.css(css)
                if ret_sel.type == "SelectorList":
                    ret.extend(ret_sel.getall())
                else:
                    ret.append(ret_sel)
            return Selector(ret)

    def re(self, pattern="", compiled=None, flags=re.I, all=False, default=None):
        if compiled is None:
            compiled = re.compile(pattern, flags=flags)
        if self.type == "Selector":
            if self.text:
                l = compiled.findall(self.text)
                if not all:
                    return l[0] if len(l) else default
                else:
                    return l
            elif self.ele:
                s = self.ele.xpath(".//text()")
                s = "".join(s)
                l = compiled.findall(s)
                if not all:
                    return l[0] if len(l) else default
                else:
                    return l
            else:
                raise Exception()
        elif self.type == "SelectorList":
            ret = []
            for sel in self.lst:
                ret.append(sel.re(compiled=compiled, all=all))
            return ret