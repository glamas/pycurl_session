# coding: utf-8

import os
import smtplib
import ssl
from email import encoders
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage

context = ssl.create_default_context()

class MailSender(object):
    ''' A simple smtp clent to sent email '''

    def __init__(self, host=None, port=25, login_user=None, login_password=None, tls=False, ssl=True):
        self.smtp_client = None
        if host:
            self.set_host(host, port, tls=tls, ssl=ssl)
        if login_user and login_password:
            self.login(login_user, login_password)

    def set_host(self, host, port=25, tls=False, ssl=True):
        self.host = host
        self.port = port
        self.tls = tls
        self.ssl = ssl
        if self.tls:
            self.smtp_client = smtplib.SMTP(self.host, self.port)
            self.smtp_client.starttls(context=context)
        elif self.ssl:
            self.smtp_client = smtplib.SMTP_SSL(self.host, self.port, context=context)
        else:
            self.smtp_client = smtplib.SMTP(self.host, self.port)

    def login(self, login_user, login_password):
        self.login_user = login_user
        self.login_password = login_password
        if self.smtp_client:
            self.smtp_client.login(self.login_user, self.login_password)

    def send(self, mailfrom, mailto, subject, body, cc=None, attachs=(), minetype="text/plain", charset="utf-8"):
        ''' Args:
                mailfrom (str): send from this email
                mailto (list): send to those email, first will show "To: xxx"
                subject (str): subject or title
                body (multi): email content
                cc (list): (optional)
                attachs (tuple): (optional) element(filepath,)
                minetype (minetype): (optional)
                charset (charset): (optional) default: utf-8
        '''
        if self.smtp_client is None:
            print("no available client")
            return
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = mailfrom
        if len(mailto) == 0:
            return
        message["To"] = mailto[0]
        message.attach(MIMEText(body, "html", charset))
        for filename in attachs:
            if os.path.exists(filename):
                with open(filename, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part["Content-Type"] = "application/octet-stream"
                    part["Content-Disposition"] = "attachment; filename={0}".format(os.path.basename(filename))
                    message.attach(part)
            else:
                print("{0} not exists".format(filename))

        try:
            rsp = self.smtp_client.sendmail(mailfrom, mailto, message.as_string())
            print(rsp)
        except:
            raise