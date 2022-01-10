# coding: utf-8

from pycurl_session import Session

def qr_decode(filepath=None, url=None, session=None):
    decode_url = "https://tool.oschina.net/action/qrcode/decode"
    if session is None:
        session = Session()
    if filepath:
        rsp = session.post(url=decode_url, data={"qrcode":"@{0}".format(filepath)}, multipart=True)
    elif url:
        rsp = session.post(url=decode_url, data={"url":url}, multipart=True)
    else:
        return None
    result = rsp.json()
    if "error" in result:
        return None
    elif len(result):
        return result[0].get("text")
    return None

def get_ip(query=None, session=None):
    """ 
    Doc:
        https://ip-api.com/docs/api:json
    Usage limits:
        This endpoint is limited to 45 requests per minute from an IP address 
    """
    url = "http://ip-api.com/json"
    if query:
        url = url + "/{0}".format(query)   # ip or domain
    if session is None:
        session = Session()
    rsp = session.get(url)
    result = rsp.json()
    return result