# Schedule

- [基本用法](#基本用法)
- [API](#API)
- [扩展](#扩展)
    - [下载中间件](#下载中间件)
    - [Item管道](#Item管道)
    - [自定义Task任务](#自定义Task任务)
- [和scrapy的区别和不足](#和scrapy的区别和不足)


## 基本用法
```python
from pycurl_session.spider import Spider, Schedule, Request, FormRequest

class Test(Spider):
    def __init__(self):
        self.start_urls = ["https://github.com"]

    def parse(self, response):
        self.log(response.title)
        yield FormRequest.from_response(response, method="GET", formdata={"q": "pycurl"}, callback=self.parse_list)

    def parse_list(self, response):
        self.log(response.title)
        url = response.xpath('//ul[contains(@class, "repo-list")]/li//a/@href').get()
        yield Request(url=response.urljoin(url), callback=self.parse_detail)

    def parse_detail(self, response):
        self.log(response.title)

if __name__ == "__main__":
    settings = {}
    schedule = Schedule(settings)
    schedule.add_spider(Test)
    schedule.run()
```

## API
from pycurl_session.spider.schedule.Schedule(custom_settings={})  
    Parameters:  
        - custom_settings - 自定义设置。[可配置项参考](../pycurl_session/spider/settings.py):  
            - BOT - 用于标识cookie。默认"Spider"  
            - USER_AGENT - 默认ua，会被DEFAULT_HEADERS["user-agent"]覆盖。默认"Spider Bot"  
            - DEFAULT_HEADERS - 默认headers  
            - ROBOTSTXT_OBEY - 是否遵守robots.txt。默认True  
            - COOKIES_DEBUG - 是否打印cookie  
            - COOKIES_STORE_ENABLED - 是否保存cookie到sqlite3文件。默认True  
            - COOKIES_STORE_DB - cookie保存文件位置。默认为临时目录  
            - COOKIES_CLEAR - 启动时是否清空对应标识的cookie  
            - DOWNLOAD_TIMEOUT - 下载超时设置。默认30(second)  
            - DOWNLOAD_DELAY - 相同域名请求延时。默认0(second)  
            - REDIRECT_ENABLED - 是否自动跳转请求。默认True  
            - RETRY_TIMES - 最大重试次数，默认3  
            - RETRY_HTTP_CODES - 重试状态码。默认[500, 502, 503, 504, 522, 524, 408, 429]  
            - LOG_ENABLED - 是否记录日志。默认False  
            - LOG_FILE - 日志文件路径，需要LOG_ENABLED=True  
            - LOG_ENCODING - 日志编码。默认utf-8  
            - LOG_FORMAT - 日志格式。默认"%(asctime)s %(levelname)s [%(name)s] %(message)s"  
            - CONCURRENT_REQUESTS - 同时请求连接数。默认16  
            - DOWNLOADER_MIDDLEWARES - (list) 下载中间件  
            - ITEM_PIPELINES - (list) Item管道  

add_spider(spider, task_provider=Task, \*\*arg)  
    Parameters:  
        - spider(Spider) - Spider类  
        - task_provider(Task) - Task继承类。用于生成请求  
        - arg - spider初始化参数  

run() 启动调度请求  

session - pycurl_session.Session()实例  
settings - (dict) 全部设置  
logstat - (dict) 数据统计  

class pycurl_session.spider.Spider()  
start_request()  
    可选，生成器函数。优先于start_urls。和start_urls只取一个  
    Return:  
        - Request  

parse(response)  
    Parameters:  
        - response(Response) - 响应类  

log(msg)  
    Parameters:  
        - msg(str) - 日志信息  

closed(reason)  
    Parameters:  
        - reason(str) - 结束原因  

name - (str) 爬虫名称  
spider_id - (str) 爬虫标识，由Spider.__class__.__name__和Spider.name组成  
start_urls - (list) 初始链接。默认callback为parse()  
_session - (Session) Schedule.session  
settings - (dict) Schedule.settings  


class pycurl_session.spider.request.Request(url, callback, meta={}, dont_filter=False, \*\*args)  
    Parameters:  
        - url(str) - 请求链接  
        - callback(function) - 回调函数  
        - meta(dict) - 数据传递。以下key是特殊值  
            - cookiejar(str) - 指定cookie标识  
            - dont_redirect(bool) - 是否自动跳转  
        - dont_filter(bool) - 是否过滤  
        - \*\*args - 其他Session.get()的参数  

_run_callback(response) - 保留函数，用于调用  

class pycurl_session.spider.request.FormRequest(url, callback, meta={}, dont_filter=False, \*\*args)  
    Parameters:  
        - url(str) - 请求链接  
        - callback(function) - 回调函数  
        - meta(dict) - 数据传递。以下key是特殊值  
            - cookiejar(str) - 指定cookie标识  
            - dont_redirect(bool) - 是否自动跳转  
        - dont_filter(bool) - 是否过滤  
        - \*\*args - 其他Session.get()的参数  
            - formdata(dict) - 表单数据  

from_response(response, form_id=None, form_name="", form_num=0, method="POST", action=None, formdata=None, files=None, callback=None, \*\*args)  
    Parameters:  
        - response(Response) - 响应类  
        - form_id(str) - 表单id  
        - form_name(str) - 表单名称  
        - form_num(int) - 表单序号。依次按form_id，form_name，form_num获取表单  
        - method(str) - 请求方式  
        - action(str) - 指定表单的action。默认会从获取的表单里拿  
        - formdata(dict) - 指定表单数据  
        - files(dict) - 文件发送  
        - callback(function) - 回调函数  
        - \*\*args - 其他Session.get()的参数  
    Return:  
        - Request  

class pycurl_session.spider.exception.IgnoreRequest()  
用于下载中间件。`raise IgnoreRequest()`将丢弃Request。  

class pycurl_session.spider.exception.DropItem()  
用于Item管道。`raise DropItem()`将丢弃Item。  


class pycurl_session.spider.mailsender.MailSender(host=None, port=25, login_user=None, login_password=None, tls=False, ssl=True)  
set_host(host, port=25, tls=False, ssl=True)  
login(login_user, login_password)  
send(mailfrom, mailto, subject, body, cc=None, attachs=(), minetype="text/plain", charset="utf-8")  

## 扩展
### 下载中间件
```python
class MyDownloadMiddleware:
    def __init__(self):
        self.request_count = 0
        self.response_count = 0

    def process_request(self, request, spider):
        self.request_count += 1

    def process_response(self, request, response, spider):
        self.response_count += 1

    def process_exception(self, request, exception, spider):
        logger = spider._get_logger()
        logger.error("ERROR: {0}, {1}".format(exception.errno, exception.errmsg))

    def process_logstat(self):
        return {"my_count": {"request_count": self.request_count, "response_count": self.response_count}}

if __name__ == "__main__":
    settings = {
        "DOWNLOADER_MIDDLEWARES": ["MyDownloadMiddleware"]
    }
    schedule = Schedule(settings)
```
DOWNLOADER_MIDDLEWARES的元素支持`package_path.Class`形式。如果只有`Class`，将会尝试从当前运行文件导入。

### Item管道
```python
class ItemCount:
    def __init__(self) -> None:
        self.count = 0

    def process_item(self, item, spider):
        spider.log(item)
        self.count += 1

    def close_spider(self, spider):
        spider.log("total: " + str(self.count))

if __name__ == "__main__":
    settings = {
        "ITEM_PIPELINES": ["ItemCount"]
    }
    schedule = Schedule(settings)
```
ITEM_PIPELINES的元素支持`package_path.Class`形式。如果只有`Class`，将会尝试从当前运行文件导入。

### 自定义Task任务
```python
from pycurl_session.spider.task import TaskItem, Task

class MyTask(Task):
    def __init__(self, spider):     # Spider instance. not support other args
        super().__init__(self, spider)
        self.start_urls = []
        file_path = "url.txt"
        with open(file_path, "r") as f:
            for line in f.readline():
                self.start_urls.append(line)

    def get(self):
        if len(self.start_urls):
            url = self.start_urls.pop()
            request = Request(url=url, callback=self.spider.parse, headers={"referer": None})
            return TaskItem(self.spider.spider_id, request)
        return None

if __name__ == "__main__":
    schedule = Schedule(settings)
    schedule.add_spider(Test, task_provider=MyTask)
```
Task初始化只支持传入Spider实例，即add_spider()的第一个参数，经过实例化后传入。

## 和scrapy的区别和不足
### 功能精简
- 没有Command line tool，没有project功能
- 没有Item()/ItemLoader()
- 没有Feed exports
- 没有Spider Middleware

### 区别
- 使用pycurl.CurlMulti做多线程。Scrapy里，使用Twisted做调度

### Selector
- Selector支持re()但和Scrapy里的不一样
- Selector通过get()/getall()/re()/\[index\]获取的结果不再是Selector。Scrapy里，支持r.xpath()[0].getall()
- 没有Selector.remove_namespaces()。

### Item pipeline
- 只支持process_item()和close_spider()

### Downloader Middleware
- 只支持process_request(), process_response()和process_exception()。没有from_crawler()

### Request/FormRequest
- 参数没有body，可以通过data参数，但不支持bytes类型
- 参数没有errback。目前错误处理还不完善
- 参数没有priority/encoding/flags/cb_kwargs
- from_response()参数没有clickdata/dont_click
- 没有JsonRequest()，可以通过Request()的json_data参数

### Response
- body是str类型，只读。可以通过text设置。在Scrapy里body是bytes类型
- 没有copy()/replace()/follow()/follow_all()函数
