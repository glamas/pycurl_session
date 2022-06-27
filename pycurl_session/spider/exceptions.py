# coding: utf-8

class IgnoreRequest(Exception):
    def __init__(self):
        pass

class RetryRequest(Exception):
    def __init__(self):
        pass

class DropItem(Exception):
    def __init__(self):
        pass

class CloseSpider(Exception):
    def __init__(self, reason=None):
        self.reason = reason if reason else "cancelled"

    def __str__(self):
        return self.reason

class PerformError(Exception):
    def __init__(self, errno, errmsg):
        self.errno = errno
        self.errmsg = errmsg

    def __str__(self):
        return "ERROR ({0}, {1})".format(self.errno, self.errmsg)