# coding: utf-8

import os
import copy
import logging
import re
import platform


if platform.system() == 'Windows':
    # On windows, run this first, enable ANSI codes
    os.system('color')

class ColoredConsoleHandler(logging.StreamHandler):
    # \x1b[ or \033 - call function, 31 - function arguments, m - funtion name
    # \x1b[0;1;34m - m(0, 1, 34)
    # 30-37 text colour, 40-47 background colour
    ANSI_M_RESET = "\x1b[0m"
    ANSI_M_BLACK = "\x1b[30m"
    ANSI_M_RED = "\x1b[31m"
    ANSI_M_GREEN = "\x1b[32m"
    ANSI_M_YELLOW = "\x1b[33m"
    ANSI_M_BLUE = "\x1b[34m"
    ANSI_M_MAGENTA = "\x1b[35m"     # pink
    ANSI_M_CYAN = "\x1b[36m"
    ANSI_M_WHITE = "\x1b[37m"

    def emit(self, record):
        # Need to make a actual copy of the record
        # to prevent altering the message for other loggers
        myrecord = copy.copy(record)
        # if setStream() to other output, no colour
        if "stderr" in self.stream.name:
            levelno = myrecord.levelno
            if(levelno >= 50):  # CRITICAL / FATAL
                color = self.ANSI_M_RED
            elif(levelno >= 40):  # ERROR
                color = self.ANSI_M_RED
            elif(levelno >= 30):  # WARNING
                color = self.ANSI_M_YELLOW
            elif(levelno >= 20):  # INFO
                color = self.ANSI_M_GREEN
            elif(levelno >= 10):  # DEBUG
                color = self.ANSI_M_MAGENTA
            else:  # NOTSET and anything else
                color = self.ANSI_M_RESET
            myrecord.levelname = color + str(myrecord.levelname) + self.ANSI_M_RESET
            myrecord.module = self.ANSI_M_BLUE + str(myrecord.module) + self.ANSI_M_RESET
            myrecord.name = self.ANSI_M_BLUE + str(myrecord.name) + self.ANSI_M_RESET
            myrecord.msg = self.colour_msg(str(myrecord.msg)) + self.ANSI_M_RESET
        logging.StreamHandler.emit(self, myrecord)

    def get_code_colour(self, code):
        # response status code
        code = int(code)
        if code >= 500:
            return self.ANSI_M_RED
        elif code >= 400:
            return self.ANSI_M_CYAN
        elif code >= 300:
            return self.ANSI_M_YELLOW
        elif code >= 200:
            return self.ANSI_M_GREEN
        elif code >= 100:
            return self.ANSI_M_MAGENTA
        else:
            return self.ANSI_M_RESET

    def colour_msg(self, msg):
        c_reset = self.ANSI_M_RESET
        c_method = self.ANSI_M_CYAN
        c_url = self.ANSI_M_GREEN
        c_time = self.ANSI_M_MAGENTA
        c_times = self.ANSI_M_CYAN
        # ({0}) <{1} {2} {3}s> (referer: {4})
        m = re.match("\((.*?)\) <(.*?) (.*) (.*)s> \(referer: (.*)\)", msg)
        if m and m.group(1):
            return "{reset}({code}{0}{reset}) <{method}{1}{reset} {url}{2}{reset} {time}{3}{reset}s> (referer: {url}{4}{reset})".format(
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
                reset=c_reset, method=c_method, time=c_time, url=c_url,
                code=self.get_code_colour(m.group(1)),
            )
        # ({0}) to <Redirect {1}> from <{2} {3} {4}s> (referer: {5})
        m = re.match("\((.*?)\) to <Redirect (.*)> from <(.*?) (.*) (.*)s> \(referer: (.*)\)", msg)
        if m and m.group(1):
            return "{reset}({code}{0}{reset}) to <{method}Redirect{reset} {url}{1}{reset}> from <{method}{2}{reset} {url}{3}{reset} {time}{4}{reset}s> (referer: {url}{5}{reset})".format(
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6),
                reset=c_reset, method=c_method, time=c_time, url=c_url,
                code=self.get_code_colour(m.group(1)),
            )
        # Crawled {0} pages and handle {2} items (last minute {1} pages and {3} items), passed {4} minites
        m = re.match("Crawled (\d+) pages and handle (\d+) items \(last minute (\d+) pages and (\d+) items\), passed (\d+) minites", msg)
        if m and m.group(1):
            return "{reset}Crawled {times}{0}{reset} pages and handle {times}{2}{reset} items (last minute {times}{1}{reset} pages and {times}{3}{reset} items), passed {times}{4}{reset} minites".format(
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
                reset=c_reset, times=c_times,
            )
        # Retry #{0} [after {1}s] {2}
        m = re.match("Retry #(.*?) \[after (.*?)s\] (.*)", msg)
        if m and m.group(1):
            return "{reset}Retry {times}#{0}{reset} [after {time}{1}{reset}s] {url}{2}{reset}".format(
                m.group(1), m.group(2), m.group(3),
                reset=c_reset, times=c_times, time=c_time, url=c_url,
            )
        # Failed to process <{0} {1}>, try max time.
        m = re.match("Failed to process <(.*?) (.*)>, try max time.", msg)
        if m and m.group(1):
            return "{reset}Failed to process <{method}{0}{reset} {url}{1}{reset}>, try max time.".format(
                m.group(1), m.group(2),
                reset=c_reset, method=c_method, url=c_url,
            )
        # Failed with no retry <{0} {1}>
        m = re.match("Failed with no retry <(.*?) (.*)>", msg)
        if m and m.group(1):
            return "{reset}Failed with no retry <{method}{0}{reset} {url}{1}{reset}>".format(
                m.group(1), m.group(2),
                reset=c_reset, method=c_method, url=c_url,
            )
        # Retry [{0}] {1}
        m = re.match("Retry \[(.*)\] (.*)", msg)
        if m and m.group(1):
            return "{reset}Retry [{times}{0}{reset}] {url}{1}{reset}".format(
                m.group(1), m.group(2),
                reset=c_reset, method=c_method, times=c_times, url=c_url,
            )
        return str(msg)

log_format = "%(asctime)s %(levelname)s [%(module)s] %(message)s"

# logging.basicConfig(format='%(asctime)s [%(module)s] %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("pycurl_session")
if len(logger.handlers) == 0:
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    ch = ColoredConsoleHandler()
    ch.setFormatter(formatter)
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

from pycurl_session.client import SFTP, FTP, WebDAV
from pycurl_session.response import Response, Selector
from pycurl_session.session import Session