# Session

- [基本用法](#基本用法)
- [API](#API)
- [扩展](#扩展)
    - [自定义验证类HTTPAUTH](#自定义验证类HTTPAUTH)
- [和requests的区别和不足](#和requests的区别和不足)
    - [Session部分](#Session部分)
    - [Response部分](#Response部分)

## 基本用法
```python
from pycurl_session import Session

r = s.get(url="https://github.com")
r = r.submit_form(method="get", formdata={"q": "pycurl"})
url = r.xpath('//ul[contains(@class, "repo-list")]/li//a/@href').get()
r = s.get(url=r.urljoin(url))
print(r.title)
r.save("test.html")
```

## API
class pycurl_session.Session(session_id=None, store_cookie=True)  
    Parameters:  
        - session_id(str) - 用来标识cookie  
        - store_cookie(str) - 是否在临时目录存储sqlite文件。如果是False，将使用":memory:"  

set_cookie_db(cookie_db_path)  
    Parameters:  
        - cookie_db_path(str) - 设置sqlite文件文件路径  

set_logger(log_path=None)  
    Parameters:  
        - log_path(str) - 设置日志保存路径，默认不保存  

set_retry_times(times=3, backoff=[])  
    Parameters:  
        - times(int) - 设置重试次数  
        - backoff(list[int, float]) - 设置重试间隔  

set_timeout(timeout=60)  
    Parameters:  
        - timeout(int) - 设置超时时间  

set_proxy(proxy)  
    Parameters:  
        - proxy(str) - 设置Session代理  

prepare_curl_handle(method, url, c=None,  
        headers=None, cookies=None, auth=None, proxy=None, cert=None,  
        params=None, data=None, json=None, files=None, multipart=False,  
        timeout=None, allow_redirects=True,  
        hooks=None, stream=None, verify=True, verbose=False, quote_safe="/",  
        session_id=None)  
    Parameters:  
        - url(str) - 请求url  
        - c(Curl) - pycurl.Curl 实例。默认None，新建一个实例  
        - headers(dict) - 请求headers  
        - cookies(dict) - 请求cookies  
        - auth(HTTPAUTH) - 验证实例  
        - proxy(str) - 设置代理，单次请求  
        - cert(str) - 指定cert文件路径  
        - params(dict, str) - url添加额外的query参数  
        - data(dict, str) - post的数据。如果是字典类型，并且值的第一个字符是'@'，会被认为是文件  
        - json(dict, str) - json字典，或者包含json数据的文件(str, 例如'@json_file.txt')，或者json字符串  
        - files(dict) - post的文件，例如{'field': 'file.txt'} 或者{'field': ['file1.txt', 'file2.txt']}  
        - multipart(bool) - 是否指定按Multipart/form-data形式提交  
        - timeout(int) - 超时设置，覆盖默认的超时设置，单次有效  
        - allow_redirects(bool) - 是否允许自动跳转(301, 302)  
        - hooks - 未实现  
        - stream - 未实现  
        - verify(bool) - 是否设置ssl验证  
        - verbose(bool) - 是否显示curl的请求过程  
        - quote_safe(str) - 对query的quote()操作，设置对应的字符。默认'/'  
        - session_id(str) - 用来标识cookie  
    Return:  
        - c(curl) - 用于执行request()  

send(c)  
    Parameters:  
        - c(curl)  
    Return:  
        - Response - 返回响应类  

get(), post(), put(), patch(), options(), delete(), head()  
    默认定义的操作  
```python
def get(self, url, **args):
    c = self.prepare_curl_handle("GET", url=url, c=self.c, **args)
    response = self.send(c)
    return response
```

c - pycurl.Curl()实例  
headers - (dict) session默认headers  
retry_http_codes - (list) 默认：[500, 502, 503, 504, 522, 524, 408, 429]  
_ssl_cipher_list - (str) SSL_CIPHER_LIST设置，默认："ALL:!EXPORT:!EXPORT40:!EXPORT56:!aNULL:!LOW:!RC4:@STRENGTH"  

class pycurl_session.Response(session)  
    Parameters:  
        - session(Session) - Session实例  

xpath(xpath)  
    Parameters:  
        - xpath(str) - lxml xpath str  
    Return:  
        - Selector  

css(css)  
    Parameters:  
        - css(str) - cssselect str  
    Return:  
        - Selector  

re(pattern, flags=re.I)  
    Parameters:  
        - pattern(str) - re pattern str  
        - flags(int) - re flags  
    Return:  
        - Selector  

json()  
    Return:  
        - dict - text转dict  

urljoin(url)  
    Return:  
        - str - same as urllib.parse.urljoin  

unquote(url)  
    Return:  
        - str - same as urllib.parse.unquote  

json_loads(s)  
    Parameters:  
        - s(str)  
    Return:  
        - str - same as json.loads  

submit_form(form_id=None, form_name="", form_num=0,  
        method="POST", action=None, formdata=None, files=None,  
        ...)  
    Parameters:  
        - form_id(str) - 表单id  
        - form_name(str) - 表单名称  
        - form_num(int) - 表单序号，使用xpath('//form["{form_num}"]').get()  
        - method(str) - 提交方式  
        - action(str) - 指定action，如果是None，自动获取  
        - formdata(dict) - 指定表单数据  
        - files(dict) - 指定上传文件  
        - 其他参数同prepare_curl_handle()  
    Return:  
        - Response  

get_header(item)  
    Parameters:  
        - item(str) - 指定获取响应中headers的某个数据  
    Return:  
        - str  

save(path)  
    Parameters:  
        - path(str) - 指定相应保存的路径(按二进制保存)  

headers - (list) 相应返回的headers  
url - (str) 请求的url。如果有跳转，最后一次请求的url  
status_code - (int) 响应状态码  
content - (BytesIO) 返回的body数据  
text - (str) 返回的body数据  
content_type - (str) body数据的网页格式，不完全准确  
encoding - (str) body数据的编码，不完全准确  
cookies - (dict) 返回的cookie  
request - (dict) 请求内容，包括method, url, referer, cookies, headers  
meta - (dict) 用于Spider Request请求传递数据  
session - (str) Session实例  


class pycurl_session.response.Selector(lst=[], text="", ele=None)  
    Parameters:  
        - lst(list) - 初始化，用于返回  
        - text(str) - 初始化，传入响应字符串  
        - ele(lxml element) - 初始化  

get()  
    Return:  
        - ele - lst的第一个元素，根据lxml/css/re的处理，返回的类型不一定  

getall()  
    Return:  
        - list - 返回lst的所有内容，根据lxml/css/re的处理，返回的元素类型不一定  

xpath(xpath)  
    Parameters:  
        - xpath(str) - lxml xpath str  
    Return:  
        - Selector  

css(css)  
    Parameters:  
        - css(str) - cssselect str  
    Return:  
        - Selector  

re(pattern="", compiled=None, flags=re.I, all=False)  
    Parameters:  
        - pattern - 正则表达式  
        - compiled - 编译的正则变量，由re.compile()创建  
        - flags - re flags  
        - all - 是否只返回第一个group的数据，默认False，返回字符串，如果是True，返回的列表  
    Return:  
        - list - 由参数all决定内部元素是字符串还是列表，如果all=True，每个元素都是列表  


## 扩展
### 自定义验证类HTTPAUTH
通过继承HTTPAUTH类，并实现attach()函数
```python
from pycurl_session import Session
from pycurl_session.auth import HTTPAUTH

class MyAuth(HTTPAUTH):
    def __init__(self, bearer):
        super().__init__()
        self._bearer = bearer

    def attach(self, session, url, headers):
        if self.auth_check(url):
            if "authorization" in headers: headers.pop("authorization")
            headers.update({"authorization": "Bearer {0}".format(self._bearer)})
s = Session()
r = s.get(url, auth=MyAuth('xxx'))  ## 只需要传递一次，后续会自动带上
```

## 和requests的区别和不足
### Session部分
- auth不支持元组，只支持HTTPAUTH实列。requests支持auth=(user, pass)
- auth是一个字典，格式是{domain: HTTPAUTH}。requests里是一个元组
- files参数只支持dict{field: path} 或者{field: [pathlist, ...]}。并且data参数里，如果值的第一个字符是'@'，会认为是文件路径。requests里，value部分需要是一个元组。
- 使用prepare_curl_handle()设置curl，通过send()发送。requests里，可以通过Request.prepare()设置请求，send()发送
- data不支持分块上传函数。requests里，data可以传入一个生成器函数
- verify只支持Boolean，不支持字符串，由cert来指定路径，并且没有Session.verify，cert文件默认由certifi.where()来查找。requests里，verify可以设置路径，Session.verify可以设置默认路径，cert支持元组，包括key和certfile
- 不支持hooks逻辑。requests里，hooks参数可以指定一些callback操作
- proxy参数不一样，并且只支持字符串。requests里，参数是proxies，还支持dict，可以分别指定https和http的代理。并且可以读取环境变量的HTTP_PROXY和HTTPS_PROXY
- 不支持Adapters()。requests里，可以通过mount()单独指定Adapters
- timeout只支持单个int。requests里，timeout支持元组(connect_timeout, read_timeout)

### Response部分
- r.headers是一个list，可以通过r.get_headers(item)获取。requests里，r.headers是一个字典，可以直接通过key获取
- 不支持r.raw。requests里，设置stream=True，可以通过r.raw获取句柄
- 没有定义codes.ok之类的常量。requests里，requests.codes定义了一些常量
- 没有定义raise_for_status()主动报异常。requests里，该函数存在
- 没有r.history的实现。requests里，r.history可以跟踪跳转
- 没有r.links。requests里，r.links["next"]和r.links["last"]可以尝试获取分页的上下页(在headers里有的话)
