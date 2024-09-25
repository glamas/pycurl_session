# coding: utf-8

## default session id
BOT = "spider"

## HEADERS
USER_AGENT = "Spider Bot"
DEFAULT_HEADERS = {
    "user-agent": USER_AGENT,
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
    "accept-encoding": "gzip, deflate",
    "accept-language": "en",
}
SIMULATE_FETCH = False

## robots.txt
ROBOTSTXT_OBEY = True

## COOKIES
COOKIES_DEBUG = False
COOKIES_STORE_ENABLED = True
COOKIES_STORE_DB = None
COOKIES_CLEAR = False

## TIMEOUT and DELAY
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_DELAY = 0

## DOWNLOADER_MIDDLEWARES
DOWNLOADER_MIDDLEWARES = []

## ITEM_PIPELINES
ITEM_PIPELINES = []

## REDIRECT and RETRY
REDIRECT_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

## LOG
LOG_ENABLED = False
LOG_ENCODING = "utf-8"
LOG_FILE = None
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

## thread
CONCURRENT_REQUESTS = 16

# DFO or BFO
DEPTH_PRIORITY = 1