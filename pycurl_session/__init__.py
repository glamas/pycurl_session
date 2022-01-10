# coding: utf-8
import logging

log_format = "%(asctime)s %(levelname)s [%(module)s] %(message)s"

# logging.basicConfig(format='%(asctime)s [%(module)s] %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("pycurl_session")
if len(logger.handlers) == 0:
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

from pycurl_session.client import SFTP, FTP, WebDAV
from pycurl_session.response import Response, Selector
from pycurl_session.session import Session