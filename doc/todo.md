# pycurl_session

### requirement
- `pycurl`: 主要
- `lxml`: 解析html内容
- `cssselect`: 通过css解析html内容
- `certifi`: ssl获取证书位置

### todo
##### Session
- [x] 文件上传
- [x] http auth认证
- [x] http和socks代理
- [x] 自动编码检测，响应类型
- [x] xpath解析响应
- [x] css解析响应
- [ ] ~~cookie保存支持文件~~
- [x] cookie保存支持sqlite3
- [x] sqlite3文件位置
- [x] 表单解析和快捷提交
- [x] restful api
- [x] 日志和日志文件
- [ ] 错误处理，code：
  - [ ] 26
  - [ ] 3
  - [ ] 28 - timeout
- [x] 302跳转控制

##### Spider
- [x] callback逻辑
- [x] meta传递数据
- [x] 支持meta['cookiejar']，对请求使用独立的cookie配置
- [x] 设置和默认配置
- [x] 表单解析和快捷提交
- [x] 302跳转控制
- [x] 默认任务队列。支持Spider.start_urls, Spider.start_requests(), redis（使用默认Task()类，需要安装redis）
- [x] 自定义任务队列。继承Task()类，通过get()返回TaskItem(spider_id, Request)，在add_spider()通过第二个参数task_provider绑定
- [x] ~~数据统计~~，内置Statistics类统计
- [x] ~~多线程~~，使用curlmulti
- [x] 针对相同域名的延时请求
- [x] item pipeline，支持yield返回字典和process_item, close_spider
- [x] 中间件，支持process_request，process_response 和process_logstat（最后导出的汇总）
- [x] 重复链接判断，同时判断callback和spider
- [ ] 错误处理
- [x] robots.txt，待优化
- [x] 爬虫结束调用closed()
- [x] 日志设置和格式化

##### Spider settings
- 不支持单个爬虫内的设置
- 仅支持全部爬虫的共同设置
- 不支持爬虫内部获取设置

支持在meta的设置：
- [x] dont_redirect    是否禁止自动跳转

支持的全局设置：
- [x] ROBOTSTXT_OBEY    是否遵守robots.txt
- [x] DOWNLOAD_DELAY     请求延时，按域名
- [x] DOWNLOAD_TIMEOUT    请求超时
- [x] LOG_ENABLED
- [x] LOG_ENCODING
- [x] LOG_FILE
- [x] RETRY_HTTP_CODES，会覆盖默认
- [x] RETRY_TIMES
- [x] COOKIES_DEBUG
- [x] COOKIES_STORE_ENABLED   默认True。如果为False，sqlite3将使用内存
- [x] COOKIES_STORE_DB        保存cookie存储的sqlite3位置
- [x] COOKIES_CLEAR    启动时清除原有cookies
- [x] REDIRECT_ENABLED
- [ ] REDIRECT_MAX_TIMES   暂不支持
- [x] CONCURRENT_REQUESTS 最大同时请求数

##### spider mailsender
- [x] 设置host，port
- [x] 设置登录名，密码
- [x] 发送纯文字
- [x] 发送带附件消息
- [ ] ~~判断附件类型~~

##### client
- [ ] ftp/sftp
- [ ] ftp/sftp 错误处理
- [ ] webdav