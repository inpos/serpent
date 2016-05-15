# -*- coding: utf-8 -*-
from serpent.config import conf
from serpent.usrpwd import dbs
from serpent import errors
'''Здесь находятся функции для проверки различных вещей.'''

def validateFrom(obj, email):
    if not conf.smtp_open_relay:
        if email[1] in conf.local_domains:
            if not obj.avatarId:
                raise errors.SMTPAuthReqError()
            elif obj.avatarId != username_by_email(email):
                raise errors.SMTPBadSender(conf.smtp_email_delim.join(email))
        elif obj.avatarId:
            raise errors.SMTPBadSender(conf.smtp_email_delim.join(email))
    return True

def validateTo(obj, user):
    local = user.dest.local
    domain = user.dest.domain
    for u, f in user.protocol._to:
        if local == u.dest.local and domain == u.dest.domain:
            del user.protocol._to[user.protocol._to.index((u,f))]
    if domain in conf.local_domains and not username_by_email([local, domain]):
        raise errors.SMTPBadRcpt(conf.smtp_email_delim.join([local, domain]))
    if domain not in conf.local_domains and not obj.avatarId and not conf.smtp_open_relay:
        raise errors.SMTPNotOpenRelay()
    return True             # Адрес найден в базах пользователей
    
def username_by_email(email):
    result = None
    for db in dbs:
        result = db.username_by_email(email)
        if result:
            break
    return result
