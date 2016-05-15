# -*- coding: utf-8 -*-
from twisted.mail import smtp
### Исключения
class SMTPAuthReqError(smtp.SMTPServerError):
    '''Класс исключения. Сообщает о необходимости авторизации.'''
    def __init__(self):
        smtp.SMTPServerError.__init__(self, 550, 'Authentication required!')

class SMTPNotOpenRelay(smtp.SMTPServerError):
    def __init__(self):
        smtp.SMTPServerError.__init__(self, 550, 'Not Open Relay!')
###

SMTPBadRcpt = smtp.SMTPBadRcpt
SMTPBadSender = smtp.SMTPBadSender