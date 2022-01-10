# -*- coding: UTF-8 -*-

import os
import sqlite3
import time
import traceback
from urllib.parse import urlparse


class CacheDB(object):
    def __init__(self, db_name):
        self.db_name = db_name

        if os.path.exists(self.db_name):
            self.conn = sqlite3.connect(
                db_name, isolation_level=None, check_same_thread=False
            )
        else:
            # create db and tables
            self.conn = sqlite3.connect(
                db_name, isolation_level=None, check_same_thread=False
            )
            create_table_sql = '''
CREATE TABLE cookie (
    session_id TEXT NOT NULL,
    name       TEXT NOT NULL,
    value      TEXT,
    domain     TEXT,
    path       TEXT,
    expires    TEXT,
    UNIQUE (session_id, name, domain, path)
)
'''
            self.conn.executescript(create_table_sql)

        self.cursor = self.conn.cursor()

    def __del__(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def execute(self, sql, para=None):
        res = None
        try:
            cursor = self.conn.cursor()  # use new cursor
            if para:
                res = cursor.execute(sql, para)
            else:
                res = cursor.execute(sql)
            # cursor.close()
        except sqlite3.Error:
            traceback.print_exc()
        finally:
            return res

    def executemany(self, sql, para=None):
        res = None
        try:
            cursor = self.conn.cursor()
            if para:
                cursor.executemany(sql, para)
            else:
                cursor.executemany(sql)
            self.conn.commit()
        except sqlite3.Error:
            traceback.print_exc()
        finally:
            return res

    query = execute

    def get_cookies(self, session_id, request_url="", default={}):
        if session_id is None:
            return {}
        if request_url:
            url = request_url
        else:
            return {}
        url_parsed = urlparse(url)
        url_domain = url_parsed.netloc
        url_domain_split = url_domain.split(".")
        if len(url_domain_split) >= 2:
            top_domain = url_domain_split[-2] + "." + url_domain_split[-1]
        else:
            top_domain = url_domain.lstrip(".")
        url_path = url_parsed.path if url_parsed.path else "/"

        cookies = default if default else {}
        if cookies:
            sql = (
                "INSERT OR REPLACE INTO cookie (session_id, name, value, domain, path, expires)"
                "VALUES(?, ?, ?, ?, ?, ?)"
            )
            params = []
            for name, value in cookies.items():
                domain = url_domain
                path = "/"
                expires = ""
                params.append((session_id, name, value, domain, path, expires))
            self.executemany(sql, params)

        sql = (
            "SELECT name, value, domain, path, expires FROM cookie"
            " WHERE session_id=? AND (domain=? OR domain=? OR domain like ?) AND (expires='' OR expires>?)"
            " ORDER BY domain, path"
        )
        now = int(time.time())
        params = (session_id, top_domain, "." + top_domain, "%" + url_domain, now)
        res = self.execute(sql, params)
        for item in res.fetchall():
            path = item[3]
            if url_path.startswith(path):
                cookies.update({item[0]: item[1]})
        return cookies

    def save_cookies(self, params):
        sql = (
            "INSERT OR REPLACE INTO cookie (session_id, name, value, domain, path, expires)"
            "VALUES(?, ?, ?, ?, ?, ?)"
        )
        self.executemany(sql, params)

    def delete_cookies(self, params):
        sql = (
            "DELETE FROM cookie WHERE session_id=? and name=? and domain=? and path=?"
        )
        self.executemany(sql, params)

    def clear_cookies(self, session_id=None):
        if session_id:
            sql = "DELETE FROM cookie WHERE session_id=?"
            self.execute(sql, (session_id,))

    def unset_cookies(self, session_id, cookies=[]):
        if session_id is None:
            return
        params = []
        for cookie in cookies:
            if len(cookie) >= 2:
                name = cookie[0]
                domain = cookie[1]
                path = cookie[2] if len(cookie) >= 3 else "/"
                params.append((session_id, name, domain, path))
        if params:
            self.delete_cookies(params)
