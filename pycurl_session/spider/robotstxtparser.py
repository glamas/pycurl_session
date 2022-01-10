################################################################################
# Get idea and make code from:
#   1. urllib.robotparser.RobotFileParser()
#       Python official lib
#   2. https://github.com/scrapy/protego
#       A pure-Python robots.txt parser by scrapy
#   3. http://nikitathespider.com/python/rerp/ 
#       A robot exclusion rules parser for Python by Philip Semanchuk
#
# Usage:
#   1. Setup:
#       rp = RobotFileParser(url="https://example.com/robots.txt")
#       rp.read()
#   or
#       rp = RobotFileParser()
#       rp.set_url(url="https://example.com/robots.txt")
#       rp.read(user_agent="mybot")
#   from file:
#       rp = RobotFileParser()
#       with open("robots.txt", "r", encoding="utf-8") as f:
#           rp.parse(f.read())
#   tips:
#       1. user_agent is optional, sometimes need user_agent to download
#       2. set_url() will return a string, format: {scheme}_{hostname}_{port}
#
#   2. Check:
#       rp.can_fetch(user_agent="mybot", url="url_to_check")
#
################################################################################

import re
import time
import uuid
import urllib.parse
import urllib.request


class RobotFileParser:
    def __init__(self, url=''):
        self._user_agents = {}
        self._rule_sets = {}
        self._default_rule_sets = {
            "rule": [],
            "crawl-delay": 0,
            "request-rate": [],
        }
        self._sitemaps = []
        self.disallow_all = False
        self.allow_all = False
        self.last_checked = 0
        self.set_url(url)

    def set_url(self, url):
        self.url = url
        url_parsed = urllib.parse.urlparse(url)
        scheme = url_parsed.scheme
        hostname = url_parsed.hostname
        port = url_parsed.port
        if url_parsed.port is None:
            if url_parsed.scheme.lower() == "https":
                port = 433
            else:
                port = 80
        return "{0}_{1}_{2}".format(scheme, hostname, port)

    def read(self, user_agent=""):
        try:
            if user_agent:
                req = urllib.request.Request(self.url, None, {'User-Agent': user_agent})
            else:
                req = urllib.request.Request(self.url)
            
            f = urllib.request.urlopen(req)
            # todo encoding
            encoding = "utf-8"
            content = f.read()
            self.parse(content.decode(encoding))
            f.close()
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                self.disallow_all = True
            elif err.code >= 400 and err.code < 500:
                self.allow_all = True

    def parse(self, s):
        self.last_checked = time.time()

        s = re.sub(r"(?:\r\n)|\r|\n", "\n", s)
        lines = s.split("\n")

        last_line_user_agent = False
        rule_set_id = ""

        for line in lines:
            line = line.strip()
            # remove optional comment and strip line
            i = line.find('#')
            if i >= 0:
                line = line[:i]
            line = line.strip()
            if not line:
                continue
            line = line.split(':', 1)
            if len(line) == 2:
                field = line[0].strip().lower()
                data = urllib.parse.unquote(line[1].strip())
                if field in ("useragent", "user-agent"):
                    if last_line_user_agent is False:
                        # new user agent
                        rule_set_id = str(uuid.uuid4())
                        self._user_agents.update({data: rule_set_id})
                        self._rule_sets.update({
                            rule_set_id: {
                                "rule": [],
                                "crawl-delay": 0,
                                "request-rate": [],
                            }
                        })
                        last_line_user_agent = True
                    else:
                        # more user agent
                        self._user_agents.update({data: rule_set_id})
                elif field == "disallow":
                    last_line_user_agent = False
                    self._rule_sets[rule_set_id]["rule"].append((data, False))
                elif field == "allow":
                    last_line_user_agent = False
                    self._rule_sets[rule_set_id]["rule"].append((data, True))
                elif field == "crawl-delay":
                    last_line_user_agent = False
                    if data.strip().isdigit():
                        self._rule_sets[rule_set_id]["crawl-delay"] = int(data.strip())
                elif field == "request-rate":
                    last_line_user_agent = False
                    numbers = data.split('/')
                    if (len(numbers) == 2 and numbers[0].strip().isdigit()
                            and numbers[1].strip().isdigit()):
                        self._rule_sets[rule_set_id]["request-rate"] = [
                            int(numbers[0].strip()),
                            int(numbers[1].strip())
                        ]
                elif field == "sitemap":
                    last_line_user_agent = False
                    self._sitemaps.append(data)
        # todo sort rule

        if "*" in self._user_agents:
            self._default_rule_sets = self._rule_sets[self._user_agents["*"]]
            del self._rule_sets[self._user_agents["*"]]
            del self._user_agents["*"]

    def can_fetch(self, user_agent, url):
        if self.disallow_all:
            return False
        if self.allow_all:
            return True

        if not self.last_checked:
            return False
        _, _, path, parameters, query, fragment = urllib.parse.urlparse(url)
        url = urllib.parse.urlunparse(("", "", path, parameters, query, fragment))
        url = self._unquote_path(url)

        ## 1. find the user agent match
        ## 2. if match, follow the rule id, else use default rule set
        ## 3. loop to find the rule match
        rule_id = self._user_agent_match(user_agent)
        if rule_id:
            rule_sets = self._rule_sets[rule_id]
        elif self._default_rule_sets:
            rule_sets = self._default_rule_sets
        for path, allow in rule_sets["rule"]:
            if self._path_match(path, url):
                return allow
        return True

    def _unquote_path(self, path):
        path = re.sub("%2[fF]", "\n", path)
        path = urllib.parse.unquote(path)
        return path.replace("\n", "%2F")

    def _user_agent_match(self, user_agent):
        user_agent = user_agent.lower()
        ua_match = ""
        ua_len = 0
        for ua in self._user_agents.keys():
            if ua.lower() in user_agent and len(ua) >= ua_len:
                ua_len = len(ua)
                ua_match = ua
        if ua_match:
            return self._user_agents[ua_match]
        return None

    def _path_match(self, path, url):
        # condition 1: '*' in path or path end with "$"
        if "*" in path or path.endswith("$"):
            if path.endswith("$"):
                appendix = "$"
                path = path[:-1]
            else:
                appendix = ""
            path = re.sub(r'\*+', '*', path)
            parts = path.split("*")
            pattern = ".*".join([re.escape(p) for p in parts]) + appendix
            if re.match(pattern, url):
                return True
            return False

        # condition 2: no '*' and no "$" in path
        if "*" not in path and "$" not in path:
            if url.startswith(path):
                return True
            return False

    def crawl_delay(self, user_agent):
        if user_agent == "*":
            return self._default_rule_sets["crawl-delay"]
        elif user_agent in self._user_agents:
            return self._rule_sets[self._user_agents[user_agent]]["crawl-delay"]
        else:
            return []

    def request_rate(self, user_agent):
        if user_agent == "*":
            return self._default_rule_sets["request-rate"]
        elif user_agent in self._user_agents:
            return self._rule_sets[self._user_agents[user_agent]]["request-rate"]
        else:
            return []

    @property
    def sitemaps(self):
        return self._sitemaps[:]

    # def __str__(self):
    #     return ""
