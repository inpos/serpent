# -*- coding: utf-8 -*-

from twisted.mail import maildir, imap4
from twisted.mail.smtp import rfc822date
from twisted.internet import inotify
from twisted.python import filepath

from zope.interface import implements
from threading import Thread

import random
import email
from pickle import load, dump
from StringIO import StringIO
import os

from serpent.config import conf
from serpent import misc

from sqlitedict import SqliteDict

class LoopingTask(Thread):
    def __init__(self, func, event, interval):
        Thread.__init__(self)
        self.func = func
        self.interval = interval
        self.stopped = event

    def run(self):
        while not self.stopped.wait(self.interval):
            self.func()

class SerpentAppendMessageTask(maildir._MaildirMailboxAppendMessageTask):
    
    def moveFileToNew(self):
        while True:
            newname = os.path.join(self.mbox.path, "new", maildir._generateMaildirName())
            try:
                self.osrename(self.tmpname, newname)
                break
            except OSError, (err, estr):
                import errno
                # if the newname exists, retry with a new newname.
                if err != errno.EEXIST:
                    self.fail()
                    newname = None
                    break
        if newname is not None:
            self.mbox.lastadded = newname
            self.defer.callback(None)
            self.defer = None



class ExtendedMaildir(maildir.MaildirMailbox):
    def __iter__(self):
        return iter(self.list)

    def __getitem__(self, i):
        return self.list[i]

class IMAPMailbox(ExtendedMaildir):
    implements(imap4.IMailbox, imap4.ICloseableMailbox)
    
    AppendFactory = SerpentAppendMessageTask

    def __init__(self, path):
        maildir.initializeMaildir(path)
        self.listeners = []
        self.path = path
        self.lastadded = None
        if not os.path.exists(os.path.join(path, conf.imap_flags)):
            self.__init_flags_()
        else:
            self.__load_flags_()
            self.__check_flags()

    def _start_monitor(self):
        self.notifier = inotify.INotify()
        self.notifier.startReading()
        self.notifier.watch(filepath.FilePath(os.path.join(self.path, 'new')),
                   callbacks=[self._new_files])
        self.notifier.watch(filepath.FilePath(os.path.join(self.path,'cur')),
                   callbacks=[self._new_files])

    def _new_files(self, wo, path, code):
        if code == inotify.IN_MOVED_TO or code == inotify.IN_DELETE:
            for l in self.listeners:
                l.newMessages(self.getMessageCount(), self.getRecentCount())

    def __init_flags_(self):
        for fdir in ['new','cur']:
            for fn in os.listdir(os.path.join(self.path, fdir)):
                if fn not in self.flags['uid'].keys():
                    self.flags['uid'][fn] = self.getUIDNext()
                    if fdir == 'new':
                        self.flags['flags'][fn] = []
                    else:
                        self.flags['flags'][fn] = misc.IMAP_FLAGS['SEEN']
        self._save_flags()
        self.__load_flags_()

    def __load_flags_(self):
        with SqliteDict(conf.imap_msg_info) as msg_info, SqliteDict(conf.imap_mbox_info) as mbox_info:
            if 'subscribed' not in mbox_info.keys(): mbox_info['subscribed'] = False
            if 'uidvalidity' not in mbox_info.keys(): mbox_info['uidvalidity'] = random.randint(0, 2**32)
            if 'uidnext' not in mbox_info.keys(): mbox_info['uidnext'] = 1
            l = [l for l in self.__msg_list_()]
            for i in l:
                fn = i.split('/')[-1]
                if fn not in msg_info.keys():
                    msg_info[fn] = {'uid': self.getUIDNext()}
                    if i.split('/')[-2] == 'new':
                        msg_info[fn]['flags'] = []
                    else:
                        msg_info[fn]['flags'] = [misc.IMAP_FLAGS['SEEN']]

    def __count_flagged_msgs_(self, flag):
        c = 0
        self.__load_flags_()
        for dir in ['new','cur']:
            for fn in os.listdir(os.path.join(self.path, dir)):
                if flag in self.flags['flags'][fn]:
                    c += 1
        return c
    
    def getHierarchicalDelimiter(self):
        return misc.IMAP_HDELIM

    def getFlags(self):
        return misc.IMAP_FLAGS.values()

    def getMessageCount(self):
        self.__load_flags_()
        c = 0
        c += len([n for n in self.__msg_list_() if misc.IMAP_FLAGS['DELETED'] not in self.flags['flags'][n.split('/')[-1]]])
        return c

    def getRecentCount(self):
        return self.__count_flagged_msgs_(misc.IMAP_FLAGS['RECENT'])
    
    def getUnseenCount(self):
        return self.getMessageCount() - self.__count_flagged_msgs_(misc.IMAP_FLAGS['SEEN'])

    def isWriteable(self):
        return True

    def getUIDValidity(self):
        self.__load_flags_()
        return self.flags['uidvalidity']
    
    def getUIDNext(self):
        self.__load_flags_()
        self.flags['uidnext'] += 1
        self._save_flags()
        return self.flags['uidnext'] - 1
    
    def getUID(self, num):
        return num

    def addMessage(self, message, flags = (), date = None):
        return self.appendMessage(message).addCallback(self._cbAddMessage, flags)
    
    def _cbAddMessage(self, obj, flags):
        self.__load_flags_()
        path = self.lastadded
        self.lastadded = None
        fn = path.split('/')[-1]
        self.flags['uid'][fn] = self.getUIDNext()
        self.flags['flags'][fn] = flags
        if misc.IMAP_FLAGS['SEEN'] in flags and path.split('/')[-2] != 'cur':
            new_path = os.path.join(self.path, 'cur', fn)
            os.rename(path, new_path)
        self._save_flags()

    def __msg_list_(self):
        a = []
        for m in os.listdir(os.path.join(self.path, 'new')):
            a.append(os.path.join(self.path, 'new', m))
        for m in os.listdir(os.path.join(self.path, 'cur')):
            a.append(os.path.join(self.path, 'cur', m))
        return a

    def _seqMessageSetToSeqDict(self, messageSet):
        if not messageSet.last:
            messageSet.last = self.getMessageCount()

        seqMap = {}
        msgs = self.__msg_list_()
        for messageNum in messageSet:
            if messageNum > 0 and messageNum <= self.getMessageCount():
                seqMap[messageNum] = msgs[messageNum - 1]
        return seqMap

    def fetch(self, messages, uid):
        return [[seq, MaildirMessage(seq,
                                     file(filename, 'rb').read(),
                                     self.flags['flags'][filename.split('/')[-1]],
                                     rfc822date())]
                for seq, filename in self.__fetch_(messages, uid).iteritems()]
    def __fetch_(self, messages, uid):
        self.__load_flags_()
        if uid:
            messagesToFetch = {}
            if not messages.last:
                messages.last = self.flags['uidnext']
            for uid in messages:
                if uid in self.flags['uid'].values():
                    for name, _id in self.flags['uid'].iteritems():
                        if uid == _id:
                            if os.path.exists(os.path.join(self.path,'new', name)):
                                messagesToFetch[uid] = os.path.join(self.path,'new', name)
                            elif os.path.exists(os.path.join(self.path,'cur', name)):
                                messagesToFetch[uid] = os.path.join(self.path,'cur', name)
        else:
            messagesToFetch = self._seqMessageSetToSeqDict(messages)
        return messagesToFetch
    def store(self, messages, flags, mode, uid):
        self.__load_flags_()
        d = {}
        for _id, path in self.__fetch_(messages, uid).iteritems():
            filename = path.split('/')[-1]
            if mode < 0:
                old_f = self.flags['flags'][filename]
                self.flags['flags'][filename] = list(set(old_f).difference(set(flags)))
                if misc.IMAP_FLAGS['SEEN'] in flags and path.split('/')[-2] != 'new':
                    new_path = os.path.join(self.path, 'new', filename)
                    os.rename(path, new_path)
            elif mode == 0:
                self.flags["flags"][filename] = flags
            elif mode > 0:
                old_f = self.flags['flags'][filename]
                self.flags['flags'][filename] = list(set(old_f).union(set(flags)))
                if misc.IMAP_FLAGS['SEEN'] in flags and path.split('/')[-2] != 'cur':
                    new_path = os.path.join(self.path, 'cur', filename)
                    os.rename(path, new_path)
            self._save_flags()
            d[_id] = self.flags['flags'][filename]
        return d
    
    def expunge(self):
        self.__load_flags_()
        uids = []
        for path in self.__msg_list_():
            fn = path.split('/')[-1]
            if fn not in self.flags['uid']:
                continue
            uid = self.flags['uid'][fn]
            if misc.IMAP_FLAGS['DELETED'] in self.flags['flags'][fn]:
                os.remove(path)
                del self.flags['uid'][fn]
                del self.flags['flags'][fn]
                self._save_flags()
                uids.append(uid)
        return uids
    
    def addListener(self, listener):
        self.listeners.append(listener)

    def removeListener(self, listener):
        self.listeners.remove(listener)
    
    def requestStatus(self, names):
        return imap4.statusRequestHelper(self, names)
    
    def destroy(self):
        pass

    def close(self):
        self.notifier.stopReading()
        self.notifier.loseConnection()
        if conf.imap_expunge_on_close:
            l = self.expunge()

class MaildirMessagePart(object):
    implements(imap4.IMessagePart)
    
    def __init__(self, message):
        self.message = message
        self.data = str(message)
    
    def getHeaders(self, negate, *names):
        if not names:
            names = self.message.keys()

        headers = {}
        if negate:
            for header in self.message.keys():
                if header.upper() not in names:
                    headers[header.lower()] = self.message.get(header, '')
        else:
            for name in names:
                headers[name.lower()] = self.message.get(name, '')

        return headers

    def getBodyFile(self):
        return StringIO(self.message.get_payload())
    
    def getSize(self):
        return len(self.data)
    
    def isMultipart(self):
        return self.message.is_multipart()
    
    def getSubPart(self, part):
        return MaildirMessagePart(self.message.get_payload(part))

class MaildirMessage(MaildirMessagePart):
    implements(imap4.IMessage)

    def __init__(self, uid, message, flags, date):
        MaildirMessagePart.__init__(self, message)
        self.uid = uid
        self.message = email.message_from_string(message)
        self.flags = flags
        self.date = date
    

    def getUID(self):
        return self.uid

    def getFlags(self):
        return self.flags

    def getInternalDate(self):
        return self.date