# -*- coding: UTF-8 -*-

import os
import sqlite3
import time
import traceback
from urllib.parse import urlparse

from .utils.domain import get_tld


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

    def _query(self, sql, para=None, batch=False):
        try:
            cursor = self.conn.cursor()  # use new cursor
            if batch:
                if para:
                    cursor.executemany(sql, para)
                else:
                    cursor.executemany(sql)
            else:
                if para:
                    cursor.execute(sql, para)
                else:
                    cursor.execute(sql)
            self.conn.commit()
            return cursor
        except sqlite3.Error:
            traceback.print_exc()
        return None


    def execute(self, sql, para=None):
        return self._query(sql, para)

    def executemany(self, sql, para=None):
        return self._query(sql, para, batch=True)

    query = execute

    def get_cookies(self, session_id, request_url="", default=None):
        if session_id is None:
            return {}
        if request_url:
            url = request_url
        else:
            return {}
        url_parsed = urlparse(url)
        url_domain = url_parsed.hostname

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
            res = self.executemany(sql, params)
            if res: res.close()

        url_path = url_parsed.path if url_parsed.path else "/"
        top_domain = get_tld(url)
        domain_list = [top_domain]
        url_domain_split = url_domain.split(".")
        for i in range(len(url_domain_split)):
            subdomain = ".".join(url_domain_split[i:])
            if subdomain == top_domain:
                break
            domain_list.append(subdomain)
        domain_list.extend(["." + item for item in domain_list])
        sql = (
            "SELECT name, value, domain, path, expires FROM cookie"
            " WHERE session_id=? AND domain in ({}) AND (expires='' OR expires>?)"
            " ORDER BY domain, path"
        ).format(", ".join('?'*len(domain_list)))
        now = int(time.time())
        params = (session_id, *domain_list, now)
        res = self.execute(sql, params)
        for item in res.fetchall():
            path = item[3]
            if url_path.startswith(path):
                cookies.update({item[0]: item[1]})
        if res: res.close()
        return cookies

    def save_cookies(self, params):
        sql = (
            "INSERT OR REPLACE INTO cookie (session_id, name, value, domain, path, expires)"
            "VALUES(?, ?, ?, ?, ?, ?)"
        )
        res = self.executemany(sql, params)
        if res: res.close()

    def delete_cookies(self, params):
        sql = (
            "DELETE FROM cookie WHERE session_id=? and name=? and domain=? and path=?"
        )
        res = self.executemany(sql, params)
        if res: res.close()

    def clear_cookies(self, session_id=None):
        if session_id:
            sql = "DELETE FROM cookie WHERE session_id=?"
            res = self.execute(sql, (session_id,))
            if res: res.close()

    def unset_cookies(self, session_id, cookies=None):
        if session_id is None:
            return
        cookies = cookies or []
        params = []
        for cookie in cookies:
            if len(cookie) >= 2:
                name = cookie[0]
                domain = cookie[1]
                path = cookie[2] if len(cookie) >= 3 else "/"
                params.append((session_id, name, domain, path))
        if params:
            self.delete_cookies(params)
