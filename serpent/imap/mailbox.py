# -*- coding: utf-8 -*-

from twisted.mail import maildir, imap4
from twisted.mail.smtp import rfc822date
from twisted.internet import inotify
from twisted.python import filepath

from zope.interface import implements
from threading import Thread

import random
import email

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
            except OSError, (err, _):
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
        self.open_flags()
        self.lastadded = None
        self.__check_flags_()
    
    def open_flags(self):
        self.msg_info = SqliteDict(os.path.join(self.path, conf.imap_msg_info))
        self.mbox_info = SqliteDict(os.path.join(self.path, conf.imap_mbox_info))

    def _start_monitor(self):
        self.notifier = inotify.INotify()
        self.notifier.startReading()
        self.notifier.watch(filepath.FilePath(os.path.join(self.path, 'new')),
                   callbacks=[self._new_files])
        self.notifier.watch(filepath.FilePath(os.path.join(self.path,'cur')),
                   callbacks=[self._new_files])

    def _stop_monitor(self):
        self.notifier.stopReading()
        self.notifier.loseConnection()

    def _new_files(self, wo, path, code):
        if code == inotify.IN_MOVED_TO or code == inotify.IN_DELETE:
            for l in self.listeners:
                l.newMessages(self.getMessageCount(), self.getRecentCount())

    def __check_flags_(self):
        if 'subscribed' not in self.mbox_info.keys(): self.mbox_info['subscribed'] = False
        if 'flags' not in self.mbox_info.keys(): self.mbox_info['flags'] = []
        if 'special' not in self.mbox_info.keys(): self.mbox_info['special'] = ''
        if 'uidvalidity' not in self.mbox_info.keys(): self.mbox_info['uidvalidity'] = random.randint(0, 2**32)
        if 'uidnext' not in self.mbox_info.keys(): self.mbox_info['uidnext'] = 1
        self.mbox_info.commit(blocking=False)
        l = [l for l in self.__msg_list_()]
        for i in l:
            fn = i.split('/')[-1]
            if fn not in self.msg_info.keys():
                val1 = {'uid': self.getUIDNext()}
                if i.split('/')[-2] == 'new':
                    val1['flags'] = []
                else:
                    val1['flags'] = [misc.IMAP_FLAGS['SEEN']]
                self.msg_info[fn] = val1
        self.msg_info.commit(blocking=False)

    def subscribe(self):
        self.mbox_info['subscribed'] = True
        self.mbox_info.commit(blocking=False)

    def unsubscribe(self):
        self.mbox_info['subscribed'] = False
        self.mbox_info.commit(blocking=False)
    
    def is_subscribed(self):
        return self.mbox_info['subscribed']

    def __count_flagged_msgs_(self, flag):
        val1 = [0 for fn in self.msg_info.keys() if flag in self.msg_info[fn]['flags']]
        return len(val1)
    
    def getHierarchicalDelimiter(self):
        return misc.IMAP_HDELIM

    def setSpecial(self, special):
        self.mbox_info['special'] = special
        self.mbox_info.commit(blocking=False)

    def getFlags(self):
        return sorted(misc.IMAP_FLAGS.values())
    
    def getMboxFlags(self):
        f = list(self.mbox_info['flags'])
        if self.mbox_info['special'] != '': f.append(self.mbox_info['special'])
        return f
    
    def addFlag(self, flag):
        self.mbox_info['flags'] = list(set(self.mbox_info['flags']).union([flag]))
        self.mbox_info.commit(blocking=False)
    
    def removeFlag(self, flag):
        self.mbox_info['flags'] = list(set(self.mbox_info['flags']).difference([flag]))
        self.mbox_info.commit(blocking=False)
    
    def hasChildren(self):
        flags = self.getFlags()
        if misc.MBOX_FLAGS['HASCHILDREN'] not in flags:
            self.addFlag(misc.MBOX_FLAGS['HASCHILDREN'])
        if misc.MBOX_FLAGS['HASNOCHILDREN'] in flags:
            self.removeFlag(misc.MBOX_FLAGS['HASNOCHILDREN'])
    def hasNoChildren(self):
        flags = self.getFlags()
        if misc.MBOX_FLAGS['HASNOCHILDREN'] not in flags:
            self.addFlag(misc.MBOX_FLAGS['HASNOCHILDREN'])
        if misc.MBOX_FLAGS['HASCHILDREN'] in flags:
            self.removeFlag(misc.MBOX_FLAGS['HASCHILDREN'])

    def getMessageCount(self):
        val1 = [0 for fn in self.msg_info.keys() if misc.IMAP_FLAGS['DELETED'] not in self.msg_info[fn]['flags']]
        return len(val1)

    def getRecentCount(self):
        c = 0
        for fn in self.msg_info.keys():
            if misc.IMAP_FLAGS['RECENT'] in self.msg_info[fn]['flags']:
                c += 1
                info = self.msg_info[fn]
                info['flags'] = set(info['flags']).difference(set([misc.IMAP_FLAGS['RECENT']]))
                self.msg_info[fn] = info
        self.msg_info.commit(blocking=False)
        return c
    
    def getUnseenCount(self):
        return self.getMessageCount() - self.__count_flagged_msgs_(misc.IMAP_FLAGS['SEEN'])

    def isWriteable(self):
        return True

    def getUIDValidity(self):
        return self.mbox_info['uidvalidity']
    
    def getUIDNext(self):
        un = self.mbox_info['uidnext']
        self.mbox_info['uidnext'] += 1
        self.mbox_info.commit(blocking=False)
        return un
    
    def getUID(self, num):
        return num

    def addMessage(self, message, flags = (), date = None):
        return self.appendMessage(message).addCallback(self._cbAddMessage, flags)
    
    def _cbAddMessage(self, obj, flags):
        path = self.lastadded
        self.lastadded = None
        fn = path.split('/')[-1]
        self.msg_info[fn] = {'uid': self.getUIDNext(), 'flags': flags}
        self.msg_info.commit(blocking=False)
        if misc.IMAP_FLAGS['SEEN'] in flags and path.split('/')[-2] != 'cur':
            new_path = os.path.join(self.path, 'cur', fn)
            os.rename(path, new_path)

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
                                     self.msg_info[filename.split('/')[-1]]['flags'],
                                     rfc822date())]
                for seq, filename in self.__fetch_(messages, uid).iteritems()]
    def __fetch_(self, messages, uid):
        if uid:
            messagesToFetch = {}
            if not messages.last:
                messages.last = self.mbox_info['uidnext']
            fn_uid = dict((fn, self.msg_info[fn]['uid']) for fn in self.msg_info.keys())
            for uid in messages:
                if uid in fn_uid.values():
                    for name, _id in fn_uid.iteritems():
                        if uid == _id:
                            if os.path.exists(os.path.join(self.path,'new', name)):
                                messagesToFetch[uid] = os.path.join(self.path,'new', name)
                            elif os.path.exists(os.path.join(self.path,'cur', name)):
                                messagesToFetch[uid] = os.path.join(self.path,'cur', name)
        else:
            messagesToFetch = self._seqMessageSetToSeqDict(messages)
        return messagesToFetch
    def store(self, messages, flags, mode, uid):
        d = {}
        for _id, path in self.__fetch_(messages, uid).iteritems():
            filename = path.split('/')[-1]
            if mode < 0:
                old_f = self.msg_info[filename]
                old_f['flags'] = list(set(old_f['flags']).difference(set(flags)))
                self.msg_info[filename] = old_f
                if misc.IMAP_FLAGS['SEEN'] in flags and path.split('/')[-2] != 'new':
                    new_path = os.path.join(self.path, 'new', filename)
                    os.rename(path, new_path)
            elif mode == 0:
                old_f = self.msg_info[filename]
                old_f['flags'] = flags
                self.msg_info[filename] = old_f
            elif mode > 0:
                old_f = self.msg_info[filename]
                old_f['flags'] = list(set(old_f['flags']).union(set(flags)))
                self.msg_info[filename] = old_f
                if misc.IMAP_FLAGS['SEEN'] in flags and path.split('/')[-2] != 'cur':
                    new_path = os.path.join(self.path, 'cur', filename)
                    os.rename(path, new_path)
            d[_id] = self.msg_info[filename]['flags']
        self.msg_info.commit(blocking=False)
        return d
    
    def expunge(self):
        uids = []
        for path in self.__msg_list_():
            fn = path.split('/')[-1]
            if fn not in self.msg_info.keys():
                continue
            uid = self.msg_info[fn]['uid']
            if misc.IMAP_FLAGS['DELETED'] in self.msg_info[fn]['flags']:
                os.remove(path)
                del self.msg_info[fn]
                uids.append(uid)
        self.msg_info.commit(blocking=False)
        return uids
    
    def addListener(self, listener):
        self.listeners.append(listener)
        return True

    def removeListener(self, listener):
        self.listeners.remove(listener)
        return True
    
    def requestStatus(self, names):
        return imap4.statusRequestHelper(self, names)
    
    def destroy(self):
        pass

    def close(self):
        if len(self.listeners) == 0:
            self._stop_monitor() 
            if conf.imap_expunge_on_close:
                self.expunge()

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