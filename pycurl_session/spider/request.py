# coding: utf-8

from pycurl_session.response import Response


class Request(object):
    def __init__(self, url, method="GET", callback=None, meta=None, 
        body=None, data=None, json=None, headers=None, cookies=None,
        dont_filter=False, cb_kwargs=None,
        # encoding="utf-8", errback=None,
    ):
        ''' Request: url, method, callback, meta, headers, cookies, dont_filter, cb_kwargs'''
        self.url = url
        self.callback = callback
        self.meta = meta or {}
        # body > data > json
        _data = None
        if body: _data = body
        elif data: _data = data
        if not _data and json and method == "GET":
            # only json data, change method from GET to POST
            method = "POST"
        self.method = method
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.body = body
        self.data = _data
        self.json = json if not _data else None
        self.dont_filter = dont_filter
        self.cb_kwargs = {}
        if cb_kwargs and isinstance(cb_kwargs, dict):
            self.cb_kwargs = cb_kwargs

    def _run_callback(self, response, **cb_kwargs):
        if self.callback and callable(self.callback):
            return self.callback(response, **cb_kwargs)
        else:
            return None


class FormRequest(Request):
    def __init__(self, url, **args):
        super().__init__(self, url, **args)

    @classmethod
    def from_response(cls, response: Response,
        formid=None, formname="", formxpath="", formcss="", formnumber=0,
        method="POST", action=None, formdata=None, callback=None,
        **args
    ):
        if not isinstance(response, Response):
            raise Exception("Wrong Response")
        form = response._get_form(formid, formname, formxpath, formcss, formnumber)
        action = response._get_form_action(form, action)
        _form_data = response._get_form_inputs(form)
        if isinstance(formdata, dict):
            _form_data.update(formdata)
        if method.lower() == "get":
            query = "&".join(["{0}={1}".format(k, v) for k, v in _form_data.items()])
            if "?" in action:
                action = action + "&" + query
            else:
                action = action + "?" + query
            _form_data = None
        request_args = {
            "method": method,
            "data": _form_data,
            "callback": callback,
        }
        request_args.update(args)
        return Request(url=action, **request_args)
