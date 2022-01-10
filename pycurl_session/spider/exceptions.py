# coding: utf-8

class IgnoreRequest(Exception):
    def __init__(self):
        pass

class DropItem(Exception):
    def __init__(self):
        pass

class CloseSpider(Exception):
    def __init__(self):
        pass