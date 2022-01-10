# pycurl_session
本项目是对pycurl进行了封装，目的是使pycurl可以像requests.Session和scrapy一样使用，但功能精简。  
本项目是业余开发，功能上会不完善，请谨慎使用。  
本项目没有发布到pypi等分发平台。  

## 依赖
- pycurl -- 主要。windows的第三方编译版本可以从[这里下载](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pycurl)
- lxml -- 通过xpath解析html内容
- cssselect -- 通过css解析html内容
- certifi -- ssl获取证书位置

## 安装
下载项目内的目录pycurl_session到需要引用的地方。或者
```sh
git clone https://github.com/glamas/pycurl_session
cd pycurl_session
python setup.py install
```

## 使用
使用`Session`类，可以参考[Session](./doc/Session.zh-CN.md)
```python
from pycurl_session import Session

s = Session()
r = s.get(url)
print(r)
r.save("test.html")
```
使用`Schedule`类，可以参考[Schedule](./doc/Schedule.zh-CN.md)
```python
from pycurl_session.spider import Spider, Schedule

class Test(Spider):
    def __init__(self):
        self.start_urls = []

    def parse(self, response):
        self.log(response.title)

if __name__ == "__main__":
    settings = {}
    schedule = Schedule(settings)
    schedule.add_spider(Test)
    schedule.run()
```

## 特点
`Session`类，简化版本的requests.Session
- [x] 文件上传
- [x] http auth认证
- [x] http和socks代理
- [x] 自动编码检测，响应类型
- [x] xpath解析响应
- [x] css解析响应
- [x] 使用sqlite3持久保存cookie
- [x] 表单解析和快捷提交
- [x] restful api

`Schedule`类，简化版本的scrapy
- [x] callback逻辑
- [x] meta传递数据
- [x] 支持meta['cookiejar']，对请求使用独立的cookie配置，需要持续传递
- [x] 设置和默认设置
- [x] 表单解析和快捷提交
- [x] 默认任务队列。支持Spider.start_urls, Spider.start_requests(), redis(使用默认Task类，需要安装redis)
- [x] 自定义任务队列。继承Task类，通过get()返回TaskItem(spider_id, Request)。 可以在add_spider()通过第二个参数task_provider绑定
- [x] 使用curlmulti进行多线程请求
- [x] 支持相同域名的延时请求设置(DOWNLOAD_DELAY)
- [x] item pipeline，支持yield返回字典，仅支持process_item和close_spider
- [x] 下载中间件，仅支持process_request和process_response，不支持process_exception。另外新增支持process_logstat用于统计
- [x] 重复请求判断，依据callback和spider_id组合，即不同Spider请求或者请求的callback不一样，不会被过滤
- [x] 爬虫结束调用closed()
- [x] 日志设置和自定义格式化
- [x] 内置Statistics类统计
- [x] 内置RobotFileParser类，支持robots.txt限制
- [x] 内置MailSender类，进行简单的邮件发送
- [x] 其他全局设置，请参考[Schedule](./doc/Schedule.zh-CN.md#全局设置)

其他，仅测试
`pycurl_session.client`可导入`FTP`，`SFTP`，`WEBDAV`进行对应协议请求

## 已知问题
已知的不完善的地方，请参考[Issue](./doc/Issue.md)

## 相关仓库
- [pycurl](https://github.com/pycurl/pycurl) -- A Python Interface To The cURL library
- [requests](https://github.com/psf/requests) -- A simple, yet elegant, HTTP library
- [scrapy](https://github.com/scrapy/scrapy) -- a fast high-level web crawling & scraping framework for Python

## 使用许可
[MIT](https://github.com/glamas/pycurl_session/blob/master/LICENSE) © glamas