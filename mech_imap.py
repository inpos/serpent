# -*- coding: utf-8 -*-

import os

from zope.interface import implementer

from twisted.cred import portal
from twisted.internet import protocol, ssl
from twisted.mail import imap4

from serpent.config import conf
from serpent.imap.mailbox import ExtendedMaildir
from serpent.misc import IMAP_HDELIM, IMAP_MBOX_REG, IMAP_ACC_CONN_NUM
from shutil import rmtree, move

@implementer(imap4.IAccount)
class IMAPUserAccount(object):
    def __init__(self, mdir):
        if not os.path.exists(mdir):
            os.makedirs(mdir)
        self.dir = mdir
        if self.dir in IMAP_MBOX_REG.keys():
            IMAP_MBOX_REG[self.dir][IMAP_ACC_CONN_NUM] += 1
        else:
            IMAP_MBOX_REG[self.dir] = {}
            IMAP_MBOX_REG[self.dir][IMAP_ACC_CONN_NUM] = 0
        for m in conf.imap_auto_mbox:
            if m not in IMAP_MBOX_REG[self.dir].keys():
                if isinstance(m, str):
                    m = m.encode('imap4-utf-7')
                IMAP_MBOX_REG[self.dir][m] = ExtendedMaildir(os.path.join(self.dir, m))
                IMAP_MBOX_REG[self.dir][m]._start_monitor()
                self.subscribe(m)

    def _getMailbox(self, path):
        if isinstance(path, str):
            path = path.encode('imap4-utf-7')
        fullPath = os.path.join(self.dir, path)
        mbox = ExtendedMaildir(fullPath)
        mbox._start_monitor()
        return mbox

    def listMailboxes(self, ref, wildcard):
        for box in os.listdir(self.dir):
            yield box.decode('imap4-utf-7'), self.create(box)

    def select(self, path, rw=False):
        if isinstance(path, str):
            path = path.encode('imap4-utf-7')
        if path in IMAP_MBOX_REG[self.dir].keys():
            return IMAP_MBOX_REG[self.dir][path]
        else:
            if path in os.listdir(self.dir):
                return self.create(path)
            else:
                raise imap4.NoSuchMailbox(path)
    
    def addMailbox(self, name, mbox = None):
        if mbox:
            raise NotImplementedError
        return self.create(name)

    def create(self, pathspec):
        if isinstance(pathspec, str):
            pathspec = pathspec.encode('imap4-utf-7')
        if pathspec not in IMAP_MBOX_REG[self.dir].keys():
            paths = filter(None, pathspec.split(IMAP_HDELIM))
            for accum in range(1, len(paths)):
                subpath = IMAP_HDELIM.join(paths[:accum])
                if subpath not in IMAP_MBOX_REG[self.dir].keys():
                    try:
                        IMAP_MBOX_REG[self.dir][subpath] = self._getMailbox(IMAP_HDELIM.join(paths[:accum]))
                    except imap4.MailboxCollision:
                        pass
            IMAP_MBOX_REG[self.dir][pathspec] = self._getMailbox(pathspec)
        return IMAP_MBOX_REG[self.dir][pathspec]
    
    def delete(self, pathspec):
        if isinstance(pathspec, str):
            pathspec = pathspec.encode('imap4-utf-7')
        if pathspec in conf.imap_auto_mbox:
            raise imap4.MailboxException(pathspec)
        if pathspec not in IMAP_MBOX_REG[self.dir].keys():
            raise imap4.MailboxException("No such mailbox")
        inferiors = self._inferiorNames(pathspec)
        if r'\Noselect' in IMAP_MBOX_REG[self.dir][pathspec].getFlags():
            # Check for hierarchically inferior mailboxes with this one
            # as part of their root.
            for inferior in inferiors:
                if inferior != pathspec:
                    raise imap4.MailboxException("Hierarchically inferior mailboxes exist and \\Noselect is set")
        for inferior in inferiors:
            mdir = IMAP_MBOX_REG[self.dir][inferior].path
            IMAP_MBOX_REG[self.dir][inferior].destroy()
            del IMAP_MBOX_REG[self.dir][inferior]
            rmtree(mdir)
        return True

    def rename(self, oldname, newname):
        if oldname in conf.imap_auto_mbox:
            raise imap4.MailboxException(oldname)
        if isinstance(oldname, str):
            oldname = oldname.encode('imap4-utf-7')
        if isinstance(newname, str):
            newname = newname.encode('imap4-utf-7')
        if oldname not in IMAP_MBOX_REG[self.dir].keys():
            raise imap4.NoSuchMailbox(oldname)
        inferiors = [(o, o.replace(oldname, newname, 1)) for o in self._inferiorNames(oldname)]
        for (old, new) in inferiors:
            if new in IMAP_MBOX_REG[self.dir].keys():
                raise imap4.MailboxCollision(new)
        for (old, new) in inferiors:
            move(os.path.join(self.dir, old), os.path.join(self.dir, new))
            IMAP_MBOX_REG[self.dir][new] = IMAP_MBOX_REG[self.dir][old]
            IMAP_MBOX_REG[self.dir][new].path = os.path.join(self.dir, new)
            IMAP_MBOX_REG[self.dir][new].path_msg_info = os.path.join(self.dir, conf.imap_msg_info)
            IMAP_MBOX_REG[self.dir][new].path_mbox_info = os.path.join(self.dir, conf.imap_mbox_info)
            del IMAP_MBOX_REG[self.dir][old]
        return True

    def subscribe(self, name):
        if isinstance(name, str):
            name = name.encode('imap4-utf-7')
        if name in IMAP_MBOX_REG[self.dir].keys():
            IMAP_MBOX_REG[self.dir][name].subscribe()

    def unsubscribe(self, name):
        if name in conf.imap_auto_mbox:
            raise imap4.MailboxException(name)
        if isinstance(name, str):
            name = name.encode('imap4-utf-7')
        if name in IMAP_MBOX_REG[self.dir].keys():
            IMAP_MBOX_REG[self.dir][name].unsubscribe()

    def isSubscribed(self, name):
        if isinstance(name, str):
            name = name.encode('imap4-utf-7')
        return IMAP_MBOX_REG[self.dir][name].is_subscribed()
    
    def _inferiorNames(self, name):
        name_l = name.split(IMAP_HDELIM)
        inferiors = []
        for infname in IMAP_MBOX_REG[self.dir].keys():
            if name_l == infname.split(IMAP_HDELIM)[:len(name_l)]:
                inferiors.append(infname)
        return inferiors

@implementer(portal.IRealm)
class SerpentIMAPRealm(object):
    def requestAvatar(self, avatarId, mind, *interfaces):
        if imap4.IAccount not in interfaces:
            raise NotImplementedError(
                "This realm only supports the imap4.IAccount interface.")
        mdir = os.path.join(conf.app_dir, conf.maildir_user_path % avatarId)
        avatar = IMAPUserAccount(mdir)
        return imap4.IAccount, avatar, lambda: None

###############################################################################

class IMAPServerProtocol(imap4.IMAP4Server):
    def lineReceived(self, line):
        if isinstance(line, str):
            line = line.encode('utf-8')
        print("CLIENT:", line)
        imap4.IMAP4Server.lineReceived(self, line)

    def sendLine(self, line):
        imap4.IMAP4Server.sendLine(self, line)
        if isinstance(line, str):
            line = line.encode('utf-8')
        print("SERVER:", line)
    
    def connectionLost(self, reason):
        self.setTimeout(None)
        if self.account and self.account.dir in IMAP_MBOX_REG.keys():
            IMAP_MBOX_REG[self.account.dir][IMAP_ACC_CONN_NUM] -= 1
            if IMAP_MBOX_REG[self.account.dir][IMAP_ACC_CONN_NUM] <= 0:
                for m in IMAP_MBOX_REG[self.account.dir].keys():
                    if m == IMAP_ACC_CONN_NUM:
                        continue
                    IMAP_MBOX_REG[self.account.dir][m].close()
                    del IMAP_MBOX_REG[self.account.dir][m]
                del IMAP_MBOX_REG[self.account.dir]
            self.account = None
    
    def _parseMbox(self, name):
        if isinstance(name, str):
            return name
        try:
            return name.decode('imap4-utf-7')
        except:
            #log.err()
            raise imap4.IllegalMailboxEncoding(name)
    
    def _cbCopySelectedMailbox(self, mbox, tag, messages, mailbox, uid):
        if not isinstance(mbox, IMAPMailbox):
            self.sendNegativeResponse(tag, 'No such mailbox: ' + mailbox)
        else:
            imap4.maybeDeferred(self.mbox.fetch, messages, uid
                ).addCallback(self.__cbCopy, tag, mbox
                ).addCallback(self.__cbCopied, tag, mbox
                ).addErrback(self.__ebCopy, tag
                )
    
    def __cbCopy(self, messages, tag, mbox):
        # XXX - This should handle failures with a rollback or something
        addedDeferreds = []
        fastCopyMbox = imap4.IMessageCopier(mbox, None)
        for (_id, msg) in messages:
            if fastCopyMbox is not None:
                d = imap4.maybeDeferred(fastCopyMbox.copy, msg)
                addedDeferreds.append(d)
                continue
            # XXX - The following should be an implementation of IMessageCopier.copy
            # on an IMailbox->IMessageCopier adapter.
            flags = msg.getFlags()
            date = msg.getInternalDate()
            body = imap4.IMessageFile(msg, None)
            if body is not None:
                bodyFile = body.open()
                d = imap4.maybeDeferred(mbox.addMessage, bodyFile, flags, date)
            else:
                def rewind(f):
                    f.seek(0)
                    return f
                _buffer = imap4.tempfile.TemporaryFile()
                d = imap4.MessageProducer(msg, _buffer, self._scheduler
                    ).beginProducing(None
                    ).addCallback(lambda _, b=_buffer, f=flags, d=date: mbox.addMessage(rewind(b), f, d)
                    )
            addedDeferreds.append(d)
        return imap4.defer.DeferredList(addedDeferreds)
    def __cbCopied(self, deferredIds, tag, mbox):
        ids = []
        failures = []
        for (status, result) in deferredIds:
            if status:
                ids.append(result)
            else:
                failures.append(result.value)
        if failures:
            self.sendNegativeResponse(tag, '[ALERT] Some messages were not copied')
        else:
            self.sendPositiveResponse(tag, 'COPY completed')
    def __ebCopy(self, failure, tag):
        self.sendBadResponse(tag, 'COPY failed:' + str(failure.value))
        #log.err(failure)
        
    def _cbAppendGotMailbox(self, mbox, tag, flags, date, message):
        if not isinstance(mbox, IMAPMailbox):
            self.sendNegativeResponse(tag, '[TRYCREATE] No such mailbox')
            return
        d = mbox.addMessage(message, flags, date)
        d.addCallback(self.__cbAppend, tag, mbox)
        d.addErrback(self.__ebAppend, tag)
        
    def __cbAppend(self, result, tag, mbox):
        self.sendUntaggedResponse('%d EXISTS' % mbox.getMessageCount())
        self.sendPositiveResponse(tag, 'APPEND complete')
    def __ebAppend(self, failure, tag):
        self.sendBadResponse(tag, 'APPEND failed: ' + str(failure.value))

    def _cbStatusGotMailbox(self, mbox, tag, mailbox, names):
        if isinstance(mbox, IMAPMailbox):
            
            imap4.maybeDeferred(mbox.requestStatus, names).addCallbacks(
                self.__cbStatus, self.__ebStatus,
                (tag, mailbox), None, (tag, mailbox), None
            )
        else:
            self.sendNegativeResponse(tag, "Could not open mailbox")
    def _ebStatusGotMailbox(self, failure, tag):
        self.sendBadResponse(tag, "Server error encountered while opening mailbox.")
        #log.err(failure)

    def __cbStatus(self, status, tag, box):
        line = ' '.join(['%s %s' % x for x in status.iteritems()])
        if isinstance(box, str):
            box = box.encode('imap4-utf-7')
        self.sendUntaggedResponse('STATUS %s (%s)' % (box, line))
        self.sendPositiveResponse(tag, 'STATUS complete')
    def __ebStatus(self, failure, tag, box):
        self.sendBadResponse(tag, 'STATUS %s failed: %s' % (box, str(failure.value)))

################################################################################

class SerpentIMAPFactory(protocol.Factory):
    def __init__(self, portal):
        self.portal = portal

    def buildProtocol(self, addr):
        contextFactory = None
        if conf.tls:
            tls_data = open(conf.tls_pem, 'rb').read()
            cert = ssl.PrivateCertificate.loadPEM(tls_data)
            contextFactory = cert.options()
        p = IMAPServerProtocol(contextFactory = contextFactory)
        if conf.tls:
            p.canStartTLS = True
        p.IDENT = '%s ready' % conf.SRVNAME
        p.portal = self.portal
        return p
imap_portal = portal.Portal(SerpentIMAPRealm())
