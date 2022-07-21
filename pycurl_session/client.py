# -*- coding: UTF-8 -*-

import os
import sys
import pycurl
import certifi
import re
import json
from lxml import etree
from io import BytesIO
from urllib.parse import urlparse, quote, unquote
from urllib.parse import ParseResult, urlunparse

default_port = {
    "http": 80,
    "https": 443,
    "sftp": 22,
    "ftp": 21,
}

class Client:
    ''' implement:
            login, logout, pwd, cd
    '''
    def __init__(self, url=None, login="", password=""):
        self.url = None
        self.base_url = None
        self._home = None
        self._pwd = None
        self._scheme = None
        self._username = None
        self._password = None
        self.verbose = 0
        self._quote_out = []

        self.c = pycurl.Curl()
        self.c.buffer = BytesIO()
        self.c.reset()
        self.c.setopt(pycurl.CONNECTTIMEOUT, 60)
        self.status_code = 0
        self.status = "logout"
        if url:
            self.login(url, login, password)

    def login(self, url, login="", password=""):
        self.prepare_url(url, login, password)
        # print(self.url)
        self.c.setopt(pycurl.URL, self.url)
        if self._scheme in ["ftp", "sftp"]:
            if self._username:
                self.c.setopt(pycurl.USERNAME, self._username)
            if self._password:
                self.c.setopt(pycurl.PASSWORD, self._password)
        elif self._scheme in ["http", "https"] and self._username and self._password:
            self.c.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_ANY)
            self.c.setopt(pycurl.USERPWD, "{0}:{1}".format(self._username, self._password))
        if self._scheme in ["https", "ftps"]:
            self.c.setopt(pycurl.CAINFO, certifi.where())
            # self.c.setopt(pycurl.SSL_VERIFYPEER, 0)
            self.c.setopt(pycurl.SSL_VERIFYPEER, 1)
            self.c.setopt(pycurl.SSL_VERIFYHOST, 2)
        self.status = "login"
        self.pwd()
        self._set_path(self._pwd, cd=True)

    def logout(self):
        self.status = "logout"
        self.c.close()

    def pwd(self):
        if self.status == "logout": return
        try:
            if self._home is None:
                self.c.setopt(pycurl.NOBODY, 1)
                self.c.perform()
                self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
                self.c.setopt(pycurl.NOBODY, 0)
                if self._scheme in ["ftp", "sftp"]:
                    self._home = self.c.getinfo(pycurl.FTP_ENTRY_PATH)
                else:
                    self._home = "/"
        except pycurl.error as e:
            # code, msg = e
            print(e)
            if self._home is None:
                self.status = "logout"
        if self._pwd: return self._pwd

    def cd(self, path="."):
        if self.status == "logout": return
        self._set_path(path, cd=True)
        self.url = self.url.rstrip("/") + "/"
        self.c.setopt(pycurl.URL, self.url)

    def prepare_url(self, url, login="", password=""):
        if not url:
            print("error")
            return None
        url_parsed = urlparse(url)
        scheme = url_parsed.scheme
        if scheme not in ["http", "https", "ftp", "sftp"]:
            print("scheme must be ftp or sftp, got {0}".format(scheme))
            return None

        hostname = url_parsed.hostname
        if url_parsed.port:
            port = url_parsed.port
        else:
            port = default_port[scheme]
        if port in [80, 443]:
            netloc = hostname
        else:
            netloc = "{hostname}:{port}".format(hostname=hostname, port=port)
        self.base_url = urlunparse(ParseResult(scheme, netloc, "", "", "", ""))

        self._username = url_parsed.username
        self._password = url_parsed.password
        if self._username is None and login != "":
            self._username = login
        if self._password is None and password != "":
            self._password = password

        self._pwd = url_parsed.path
        self._scheme = url_parsed.scheme
        self.url = urlunparse(ParseResult(
            scheme,
            netloc,
            quote(unquote(url_parsed.path)),
            url_parsed.params,
            url_parsed.query,
            url_parsed.fragment
        ))
        # self._set_path(self._pwd)

    def set_ua(self, useragent):
        if useragent:
            self.c.setopt(pycurl.USERAGENT, useragent)

    def _set_path(self, path, cd=False, to_quote=True):
        if self._pwd.endswith("/") and not self._pwd.endswith("\\/"):
            self._pwd = self._pwd.rstrip("/")
        new_path = ""
        if path.startswith(".."):
            new_path = self._pwd + "/" + path
        elif path.startswith("./"):
            new_path = self._pwd + path[1:]
        elif path.startswith("/"):
            new_path = path
        elif path.startswith("~"):
            new_path = self._home + path[1:]
        elif len(path) > 0:
            new_path = self._pwd + "/" + path
        if new_path:
            # print(new_path)
            tmp = []
            for item in re.split(r"(?<!\\)/", new_path):
                if item == ".":
                    continue
                if item == ".." and len(tmp) > 0:
                    tmp.pop(-1)
                    continue
                tmp.append(item)
            new_path = "/".join(tmp)
            if cd:
                self._pwd = new_path
            if to_quote:
                new_path = quote(unquote(new_path))
            self.url = "{0}{1}".format(self.base_url, new_path)
            return new_path
        else:
            self.url = "{0}{1}".format(self.base_url, self._pwd)
            return self._pwd

    def set_verbose(self, verbose):
        self.verbose = 1 if verbose else 0
        self.c.setopt(pycurl.VERBOSE, self.verbose)
        self.c.setopt(pycurl.DEBUGFUNCTION, self._debug_callback)
        self.response_headers = []
        self.c.setopt(pycurl.HEADERFUNCTION, self._header_handle)

    def _header_handle(self, header_line):
            header_line = header_line.decode("utf-8")
            self.response_headers.append(header_line.strip())

    def _debug_callback(self, debug_type, debug_msg):
        # print("{0}: {1}".format(debug_type, debug_msg))
        debug_msg = debug_msg.decode("utf-8").strip()
        if debug_type == pycurl.INFOTYPE_TEXT:  # 0
            if self.verbose: print("* {0}".format(debug_msg))
        elif debug_type == pycurl.INFOTYPE_HEADER_IN:   # 1
            print("HEADER_IN < {0}".format(debug_msg))
            self._quote_out.append(debug_msg)
        elif debug_type == pycurl.INFOTYPE_HEADER_OUT:  # 2
            print("HEADER_OUT > {0}".format(debug_msg))
        elif debug_type == pycurl.INFOTYPE_DATA_IN:     # 3
            if self.verbose: print("DATA_IN < {0}".format(debug_msg))
        elif debug_type == pycurl.INFOTYPE_DATA_OUT:    # 4
            pass
        elif debug_type == pycurl.INFOTYPE_SSL_DATA_IN: # 5
            print("SSL_DATA_IN < {0}".format(debug_msg))
            self._quote_out.append(debug_msg)
        elif debug_type == pycurl.INFOTYPE_SSL_DATA_OUT: # 6
            print("SSL_DATA_OUT > {0}".format(debug_msg))

    def xml_to_json(self, s):
        xslt = '''<?xml version="1.0" encoding="UTF-8" ?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="text" encoding="utf-8" />
    <xsl:template match="/*[1]">
        <xsl:text>{</xsl:text>
        <xsl:apply-templates select="*" mode="detect-element" />
        <xsl:text>}</xsl:text>
    </xsl:template>
    <xsl:template match="*" mode="detect-element">
        <xsl:choose>
            <xsl:when test="name(preceding-sibling::*[1]) = name() or name(following-sibling::*[1]) = name() or @json..Array or @*[name()=&apos;json:Array&apos;] ">
                <xsl:if test="name(preceding-sibling::*[1]) != name()">
                    <xsl:text>"</xsl:text>
                    <xsl:value-of select="name()" />
                    <xsl:text>":[</xsl:text>
                </xsl:if>
                <xsl:apply-templates select="." mode="output-element" />
                <xsl:if test="name(following-sibling::*[1]) != name()">
                    <xsl:text>]</xsl:text>
                </xsl:if>
            </xsl:when>
            <xsl:otherwise>
                <xsl:text>"</xsl:text>
                <xsl:value-of select="name()" />
                <xsl:text>":</xsl:text>
                <xsl:apply-templates select="." mode="output-element" /></xsl:otherwise>
        </xsl:choose>
        <xsl:if test="following-sibling::*">
            <xsl:text>,</xsl:text>
        </xsl:if>
    </xsl:template>
    <xsl:template match="*" mode="output-element">
        <xsl:choose>
            <xsl:when test="* or @*[not(starts-with(name(), &apos;json..&apos;)) and not(starts-with(name(), &apos;json:&apos;))]">
                <xsl:text>{</xsl:text>
                <xsl:if test="@*[not(starts-with(name(), &apos;json..&apos;)) and not(starts-with(name(), &apos;json:&apos;))]">
                    <xsl:apply-templates select="@*[not(starts-with(name(), &apos;json..&apos;)) and not(starts-with(name(), &apos;json:&apos;))]" mode="output-attribute" />
                    <xsl:if test="text() and normalize-space(text()) != &apos;&apos; or *">
                        <xsl:text>,</xsl:text>
                    </xsl:if>
                </xsl:if>
                <xsl:if test="text() and normalize-space(text()) != &apos;&apos;">
                    <xsl:text>"text":"</xsl:text>
                    <xsl:call-template name="output-string">
                        <xsl:with-param name="string" select="text()" /></xsl:call-template>
                    <xsl:text>"</xsl:text>
                    <xsl:if test="*">
                        <xsl:text>,</xsl:text>
                    </xsl:if>
                </xsl:if>
                <xsl:apply-templates select="*" mode="detect-element" />
                <xsl:text>}</xsl:text>
            </xsl:when>
            <xsl:otherwise>
                <xsl:choose>
                    <xsl:when test="@json..Type or @*[name()=&apos;json:Type&apos;]">
                        <xsl:value-of select="normalize-space(text())" />
                        <xsl:if test="normalize-space(text()) = &apos;&apos;">
                            <xsl:text>null</xsl:text>
                        </xsl:if>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:text>"</xsl:text>
                        <xsl:call-template name="output-string">
                            <xsl:with-param name="string" select="text()" /></xsl:call-template>
                        <xsl:text>"</xsl:text>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <xsl:template match="@*" mode="output-attribute">
        <xsl:text>"</xsl:text>
        <xsl:value-of select="name()" />
        <xsl:text>":"</xsl:text>
        <xsl:call-template name="output-string">
            <xsl:with-param name="string" select="." /></xsl:call-template>
        <xsl:text>"</xsl:text>
        <xsl:if test="position() &lt; last()">,</xsl:if>
    </xsl:template>
    <xsl:template name="output-string">
        <xsl:param name="string" />
        <xsl:if test="$string != &apos;&apos;">
            <xsl:choose>
                <xsl:when test="contains($string, &apos;&#x09;&apos;) or contains($string, &apos;&#x0A;&apos;) or contains($string, &apos;&#x0D;&apos;) or contains($string, &apos;&quot;&apos;) or contains($string, &apos;\&apos;)">
                    <xsl:choose>
                        <xsl:when test="($string = &apos;&#x09;&apos;) or ($string = &apos;&#x0A;&apos;) or ($string = &apos;&#x0D;&apos;)">
                            <xsl:text></xsl:text>
                        </xsl:when>
                        <xsl:when test="starts-with($string, &apos;&#x09;&apos;)">
                            <xsl:text>\t</xsl:text>
                        </xsl:when>
                        <xsl:when test="starts-with($string, &apos;&#x0A;&apos;)">
                            <xsl:text>\n</xsl:text>
                        </xsl:when>
                        <xsl:when test="starts-with($string, &apos;&#x0D;&apos;)">
                            <xsl:text>\r</xsl:text>
                        </xsl:when>
                        <xsl:when test="starts-with($string, &apos;&quot;&apos;)">
                            <xsl:text>\&quot;</xsl:text>
                        </xsl:when>
                        <xsl:when test="starts-with($string, &apos;\&apos;)">
                            <xsl:text>\\</xsl:text>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="substring($string, 1, 1)" /></xsl:otherwise>
                    </xsl:choose>
                    <xsl:call-template name="output-string">
                        <xsl:with-param name="string" select="substring($string, 2)" /></xsl:call-template>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:value-of select="$string" /></xsl:otherwise>
            </xsl:choose>
        </xsl:if>
    </xsl:template>
</xsl:stylesheet>
'''
        tree = etree.XML(s.encode("utf-8"))
        xslt_root = etree.XML(xslt.encode("utf-8"))
        transform = etree.XSLT(xslt_root)
        result = transform(tree)
        json_load = json.loads(str(result), strict=False)
        return json_load

class _FTP_common(Client):
    ''' implement:
            list, download, upload
    '''
    def __init__(self, url=None, login="", password=""):
        Client.__init__(self, url=url, login=login, password=password)

    def list(self, method="LIST"):
        if self.status == "logout": return
        try:
            method = method.upper()
            if method not in ["LIST", "NLST", "MLSD"]:
                return
            self.cd()   # set url
            self.c.buffer = BytesIO()
            self.c.setopt(pycurl.WRITEDATA, self.c.buffer)
            self.c.setopt(pycurl.CUSTOMREQUEST, method)
            self.c.perform()
            self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
            data = self.c.buffer.getvalue().decode("utf-8")
            print(data)
            return data
        except pycurl.error as e:
            # code, msg = e
            print(e)

    def download(self, remote_src, local_dst=None):
        if self.status == "logout": return
        try:
            self._set_path(remote_src)
            self.c.setopt(pycurl.URL, self.url)
            self.c.buffer = BytesIO()
            self.c.setopt(pycurl.WRITEDATA, self.c.buffer)
            self.c.perform()
            self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
            if local_dst is None:
                local_dst = os.path.basename(self.url)
                local_dst = unquote(local_dst)
            bytes_data = self.c.buffer.getvalue()
            with open(local_dst, "wb") as f:
                f.write(bytes_data)
            return bytes_data
        except pycurl.error as e:
            code, msg = e.args
            print(e)
            if code == 79:
                print("Error: the remote_src is not a file?")

    def upload(self, local_src, remote_dst=None):
        if self.status == "logout": return
        filename = os.path.basename(local_src)
        if remote_dst is None:
            remote_dst = self._pwd.rstrip("/") + "/"
        if remote_dst.endswith("/") and not remote_dst.endswith("\\/"):
            remote_dst = remote_dst + filename
        try:
            self._set_path(remote_dst)
            # print(self.url)
            self.c.setopt(pycurl.URL, self.url)
            self.c.setopt(pycurl.UPLOAD, 1)
            self.c.setopt(pycurl.FTP_CREATE_MISSING_DIRS, 1)
            with open(local_src, "rb") as f:
                self.c.setopt(pycurl.READDATA, f)
                self.c.perform()
                self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
        except pycurl.error as e:
            code, msg = e.args
            print(e)
        except Exception as e:
            print(e)
        finally:
            self.c.setopt(pycurl.UPLOAD, 0)
            self.c.setopt(pycurl.FTP_CREATE_MISSING_DIRS, 0)

class SFTP(_FTP_common):
    ''' implement:
            Client: login, logout, pwd, cd
            _FTP_common: list, download, upload
            SFTP: exists, mkdir, rmdir, rename, delete
    '''
    def __init__(self, url=None, login="", password=""):
        _FTP_common.__init__(self, url, login, password)

    def exists(self, remote_src):
        if self.status == "logout": return
        exists = False
        try:
            self._set_path(remote_src)
            self.c.setopt(pycurl.URL, self.url)
            self.c.setopt(pycurl.NOBODY, 1)
            self.c.setopt(pycurl.OPT_FILETIME, 1)
            self.c.perform()
            self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
            t = self.c.getinfo(pycurl.INFO_FILETIME)
            if t and t != -1: exists = True
        except pycurl.error as e:
            # code, msg = e.args
            print(e)
        finally:
            self.c.setopt(pycurl.NOBODY, 0)
            return exists

    def _directory_action(self, action, path):
        if self.status == "logout": return
        if action.lower() not in ["mkdir", "rmdir"]:
            print("Error: action invalidate")
            return
        try:
            new_path = self._set_path(path)
            # print(action, self.url)
            self.c.setopt(pycurl.QUOTE, ["{0} {1}".format(action.lower(), new_path)])
            self.c.setopt(pycurl.NOBODY, 1)
            self.c.setopt(pycurl.URL, self.url)
            self.c.perform()
            self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
        except pycurl.error as e:
            code, msg = e.args
            if code == 21:
                if action.lower() == "rmdir" and "no such" in msg.lower():
                    # rmdir success
                    pass
                elif action.lower() == "mkdir" and "operation failed" in msg.lower():
                    # mkdir exists
                    pass
                elif "permission denied" in msg.lower():
                    print(e)
                else:
                    print(e)
        finally:
            self.c.setopt(pycurl.NOBODY, 0)
            self.c.setopt(pycurl.QUOTE, ["pwd"])    # bug: cannot be set to None

    def mkdir(self, path):
        return self._directory_action("mkdir", path)

    def rmdir(self, path):
        return self._directory_action("rmdir", path)

    def _file_action(self, action, src, dst=None):
        if self.status == "logout": return
        if action.lower() not in ["rm", "rename"]:
            print("Error: action invalidate")
            return
        if action.lower() in ["rename"] and dst is None:
            print("Error: dst need")
        try:
            src_new = self._set_path(src)
            if dst:
                dst_new = self._set_path(dst)
            print(action, self.url)
            if dst:
                self.c.setopt(pycurl.QUOTE, ["{0} {1} {2}".format(action.lower(), src_new, dst_new)])
            else:
                self.c.setopt(pycurl.QUOTE, ["{0} {1}".format(action.lower(), src_new)])
            self.c.setopt(pycurl.NOBODY, 1)
            self.c.setopt(pycurl.URL, self.url)
            self.c.perform()
            self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
        except pycurl.error as e:
            code, msg = e.args
            print(e)
        finally:
            self.c.setopt(pycurl.NOBODY, 0)
            self.c.setopt(pycurl.QUOTE, ["pwd"])    # bug: cannot be set to None

    def rename(self, src, dst):
        self._file_action("rename", src, dst)

    def delete(self, src):
        self._file_action("rm", src)


class FTP(_FTP_common):
    ''' implement:
            Client: login, logout, pwd, cd
            _FTP_common: list, download, upload
            FTP: mkdir, rmdir, rename, delete
    '''
    def __init__(self, url=None, login="", password=""):
        _FTP_common.__init__(self, url, login, password)

    def _action(self, action, src=None, dst=None, nobody=True):
        ''' https://www.ietf.org/rfc/rfc959.txt
        action:
            str: will use src and dst, other will not.
                e.g. list
            list: pipeline command, if 1st is not 0, 1st is cmd, rest will pass to _set_path();
                    if 1st is 0, 2nd is cmd, rest will not pass to _set_path()
                e.g.[(list),(DELE, path),(0, mark, a, b)]
        '''
        if self.status == "logout": return
        opt_quote = []
        if isinstance(action, str):
            cmd = [action.upper()]
            if src: cmd.append(self._set_path(src, to_quote=False))
            if dst: cmd.append(self._set_path(dst, to_quote=False))
            opt_quote.append(" ".join(cmd))
        elif isinstance(action, list):
            for act in action:
                if len(act) == 1:
                    opt_quote.append(act[0])
                elif len(act) >= 2 and act[0] != 0:
                    act = list(act)
                    cmd = [act.pop(0)]
                    cmd.extend([self._set_path(item, to_quote=False) for item in act])
                    opt_quote.append(" ".join(cmd))
                elif len(act) >= 2 and act[0] == 0:
                    act = list(act)
                    act.pop(0)
                    cmd = [act.pop(0)]
                    cmd.extend([self._set_path(item, to_quote=False) for item in act])
                    opt_quote.append(" ".join(cmd))
        self._set_path(self._pwd)
        # print(self.url)
        if len(opt_quote) == 0:
            return
        try:
            self.response_headers = []
            opt_quote = [item.encode("utf-8") for item in opt_quote]
            # print(opt_quote)
            self.c.setopt(pycurl.QUOTE, opt_quote)
            self.c.setopt(pycurl.NOBODY, nobody)
            self.c.setopt(pycurl.URL, self.url)
            self.c.perform()
            self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
            # print(self.response_headers)
        except pycurl.error as e:
            code, msg = e.args
            print(e)
        finally:
            self.response_headers = []
            self.c.setopt(pycurl.NOBODY, 0)
            self.c.setopt(pycurl.QUOTE, ["NOOP"])    # bug: cannot be set to None

    def mkdir(self, path):
        return self._action("MKD", path)

    def rmdir(self, path):
        return self._action("RMD", path)

    def rename(self, src, dst):
        return self._action([("RNFR", src),("RNTO", dst)])

    def delete(self, src):
        return self._action("DELE", src)


class WebDAV(Client):
    ''' implement:
            Client: login, logout, pwd, cd
            WebDAV: list, download, upload, mkdir, rmdir, rename, delete
    '''
    def __init__(self, url=None, login="", password=""):
        Client.__init__(self, url=url, login=login, password=password)

    def list(self, to_json=False):
        if self.status == "logout": return
        try:
            self.cd()   # set url
            self.c.buffer = BytesIO()
            self.c.setopt(pycurl.WRITEDATA, self.c.buffer)
            self.c.setopt(pycurl.CUSTOMREQUEST, "PROPFIND")
            self.c.setopt(pycurl.HTTPHEADER, ["Depth: 1"])
            self.c.perform()
            self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
            data = self.c.buffer.getvalue().decode("utf-8")
            if self.status_code >=200 and self.status_code < 300 and to_json:
                data = self.xml_to_json(data)
            print(json.dumps(data, indent=2))
            return data
        except pycurl.error as e:
            # code, msg = e
            print(e)
        finally:
            self.c.setopt(pycurl.UPLOAD, 0)
            self.c.setopt(pycurl.HTTPHEADER, None)

    def _action(self, method="GET", src=None, dst=None):
        if self.status == "logout": return
        try:
            method = method.upper()
            ## "GET", "POST", "PUT", "DELETE", "PROPFIND", "PROPPATCH", "MKCOL", "COPY", "MOVE", "LOCK", "UNLOCK"
            if method not in ["GET", "PUT", "DELETE", "PROPFIND", "MKCOL", "MOVE"]:
                return
            if method in ["PUT", "MOVE"]:
                if not dst:
                    return
                if method == "PUT":
                    with open(dst, "rb") as f:
                        data_body = f.read()
                    self.c.setopt(pycurl.POSTFIELDS, data_body)
                else:
                    dst = self._set_path(dst)
                    self.c.setopt(pycurl.HTTPHEADER, ["Destination: {0}".format(dst)])
            if src:
                src = self._set_path(src)
                self.c.setopt(pycurl.URL, self.url)
                if method in ["PROPFIND"]:
                    self.c.setopt(pycurl.HTTPHEADER, ["Depth: 1"])
            else:
                self.cd()   # set url
            self.c.buffer = BytesIO()
            self.c.setopt(pycurl.WRITEDATA, self.c.buffer)
            self.c.setopt(pycurl.CUSTOMREQUEST, method)
            self.c.perform()
            self.status_code = self.c.getinfo(pycurl.RESPONSE_CODE)
            raw_data = self.c.buffer.getvalue()
            if method == "GET" and dst:
                with open(dst, "wb") as f:
                    f.write(raw_data)
                return raw_data
            else:
                data = raw_data.decode("utf-8")
                # print(data)
                return data
        except pycurl.error as e:
            # code, msg = e
            print(e)
        finally:
            self.c.setopt(pycurl.UPLOAD, 0)
            self.c.setopt(pycurl.HTTPHEADER, None)

    def download(self, src, dst):
        if self.status == "logout": return
        return self._action("GET", src=src, dst=dst)

    def upload(self, local_src, remote_dst=None):
        if self.status == "logout": return
        filename = os.path.basename(local_src)
        if remote_dst is None:
            remote_dst = self._pwd.rstrip("/") + "/"
        if remote_dst.endswith("/") and not remote_dst.endswith("\\/"):
            remote_dst = remote_dst + filename
        return self._action("PUT", src=remote_dst, dst=local_src)

    def delete(self, src, is_dir=False):
        if is_dir:
            return self.rmdir(src)
        return self._action("DELETE", src)

    def rename(self, src, dst):
        return self._action("MOVE", src, dst)

    def mkdir(self, path):
        return self._action("MKCOL", src=path)

    def rmdir(self, path):
        if not path.endswith("/"):
            path = path + "/"
        return self._action("DELETE", path)