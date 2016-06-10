# -*- coding: utf-8 -*-
MSG_ACTIVE = 0
MSG_FROZEN = 1

IMAP_FLAGS = {
    'SEEN':     '\\Seen',
    'FLAGGED':  '\\Flagged',
    'ANSWERED': '\\Answered',
    'RECENT':   '\\Recent',
    'DELETED':  '\\Deleted',
    'DRAFT':    '\\Draft'    
    }
MBOX_FLAGS = {
    'NOINFERIORS': '\\Noinferiors',
    'NOSELECT': '\\Noselect',
    'MARKED': '\\Marked',
    'UNMARKED': '\\Unmarked',
    'HASCHILDREN': '\\HasChildren',
    'HASNOCHILDREN': '\\HasNoChildren'
    }
IMAP_HDELIM = '.'
IMAP_ACC_CONN_NUM = '...ConnectionUUID...'
IMAP_MBOX_REG = {}