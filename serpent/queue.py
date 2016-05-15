# -*- coding: utf-8 -*-
from serpent.config import conf
from serpent import dataio, misc, rules
from datetime import datetime, timedelta
from os import path

class SmtpQueue(object):
    def __init__(self, store, local_delivery):
        self.stor = store
        self.local_delivery = local_delivery

    def add(self, data):
        '''Ставит письмо в очередь'''
        data['add_time'] = datetime.utcnow()
        data['state'] = misc.MSG_ACTIVE
        w = self.stor.write(data)
        if not w:
            return False
        return self.__process_(data['id'])
    
    def run(self):
        '''Запускает обработку очереди'''
        now = datetime.utcnow()
        check_delta = timedelta(minutes = conf.smtp_queue_check_period)
        expire_delta = timedelta(minutes = conf.smtp_queue_message_ttl)
        for mid in self.__list_messages_():
            info = self.stor.getinfo(mid)
            if (now - info['add_time']) >= expire_delta:
                self.stor.delete(mid)
                continue
            if (now - info['add_time']) >= check_delta:
                continue
            self.__process_(mid)
        return True
    
    def __local_deliver_(self, mid):
        message = self.stor.read(mid)
        user = rules.username_by_email(message['rcpt'])
        return self.local_delivery.deliver(user, message['message'])
    
    def __send_email_(self, mid):
        pass
    
    def __freeze_(self, mid):
        info = self.stor.getinfo(mid)
        if info:
            if info['state'] != misc.MSG_FROZEN :
                info['state'] = misc.MSG_FROZEN
                if self.stor.setinfo(info):
                    return True
            else:
                return True
        return False
    
    def __process_(self, mid):
        info = self.stor.getinfo(mid)
        if info:
            if info['rcpt'][1] in conf.local_domains:
                if self.__local_deliver_(mid):
                    self.__remove_message_(mid)
                    return True
                else:
                    return self.__freeze_(mid)
            else:
                if self.__send_email_(mid):
                    self.__remove_message_(mid)
                    return True
                else:
                    return self.__freeze_(mid)
        return False
    
    def __list_messages_(self):
        return self.stor.list()
    
    def __remove_message_(self, mid):
        self.stor.delete(mid)

mailstore = dataio.MailDirStore()
squeue = SmtpQueue(dataio.SmtpFileStore(path.join(conf.app_dir, conf.smtp_queue_dir)),
                   mailstore)
