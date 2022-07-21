# Client

- [功能实现](#功能实现)
- [用法](#用法)

## 功能实现
SFTP:  
    login, logout, pwd, cd  
    list, download, upload  
    exists, mkdir, rmdir, rename, delete  
FTP:  
    login, logout, pwd, cd  
    list, download, upload  
    mkdir, rmdir, rename, delete  
WebDAV:  
    login, logout, pwd, cd
    list, download, upload, mkdir, rmdir, rename, delete

## 用法
```python
from pycurl_session.client import WebDAV

url = "https://example.com"
username = "username"
password = "password"
ua = "Mozilla/5.0"
s = WebDAV(url, username, password)
# or: 
# s = WebDAV()
# s.login(url, username, password)
s.set_ua(ua)                # optional.
s.set_verbose(1)            # optional. libcurl verbose.
r = s.list()                # for WebDAV, output type is xml
s.cd("path")
print(s.pwd())              # relative path. e.g. /path/
r = s.list(to_json=True)    # only for WebDAV. Convert xml to json
```
