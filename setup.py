# coding: utf-8

from setuptools import setup, find_packages

setup(
    name='pycurl_session',
    version='0.7.1',
    description='Base on pycurl, session like requests, spider like scrapy',
    url='https://github.com/glamas/pycurl_session',
    author='glamas',
    author_email='lzgug2@outlook.com',
    license='MIT',
    keywords='pycurl session spider',
    packages=find_packages(),
    install_requires=['pycurl', 'lxml', 'certifi', 'cssselect'],
    python_requires='>=3'
)