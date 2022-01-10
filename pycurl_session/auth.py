# coding: utf-8

import pycurl
from urllib.parse import urlparse


class HTTPAUTH(object):
    def __init__(self):
        self.domain: str = None
        self.path: str = None

    def auth_check(self, url):
        url_info = urlparse(url)
        if self.domain is None:
            self.domain = url_info.netloc
        if self.domain != url_info.netloc:
            return False
        return True

    def attach(self, session, url, headers):
        pass


class HTTPAUTH_BASIC(HTTPAUTH):
    def __init__(self, username, password):
        super().__init__()
        self._username = username
        self._password = password

    def attach(self, session, url, headers):
        if self.auth_check(url):
            session.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
            session.setopt(
                pycurl.USERPWD, "{0}:{1}".format(self._username, self._password)
            )


class HTTPAUTH_NTLM(HTTPAUTH):
    def __init__(self, username, password):
        super().__init__()
        self._username = username
        self._password = password

    def attach(self, session, url, headers):
        if self.auth_check(url):
            session.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_NTLM)
            session.setopt(
                pycurl.USERPWD, "{0}:{1}".format(self._username, self._password)
            )


class HTTPAUTH_DIGEST(HTTPAUTH):
    def __init__(self, username, password):
        super().__init__()
        self._username = username
        self._password = password

    def attach(self, session, url, headers):
        if self.auth_check(url):
            session.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_DIGEST)
            session.setopt(
                pycurl.USERPWD, "{0}:{1}".format(self._username, self._password)
            )


class HTTPAUTH_BEARER(HTTPAUTH):
    def __init__(self, bearer):
        super().__init__()
        self._bearer = bearer

    def attach(self, session, url, headers):
        if self.auth_check(url):
            # session.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BEARER)
            # session.setopt(pycurl.XOAUTH2_BEARER, "{0}".format(self._bearer))     # not work
            if "authorization" in headers: headers.pop("authorization")
            headers.update({"authorization": "Bearer {0}".format(self._bearer)})
            # session.setopt(pycurl.HTTPHEADER, headers)
