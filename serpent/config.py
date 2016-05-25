# -*- coding: utf-8 -*-
class Config(object):
    pass

conf = Config()
conf.VERSION = '0.1.0'
conf.SRVNAME = 'Serpent'
conf.srv_version = '%s %s' % (conf.SRVNAME, conf.VERSION)
conf.local_domains = ['dom.lan']    # Список доменов, для которых будет приниматься почта
conf.tls = True
conf.tls_pem = './serpent.pem'
conf.smtp_open_relay = False        # Разрешить ли пересылку откуда угодно куда угодно
conf.smtp_email_delim = '@'
conf.smtp_header = '''from [{sender_ip}] (helo={sender_host})
    by {srv_host} with ESMTP ({srv_info})
    (envelope-from <{sender}>)
    id {id}
    for {rcpt}; {date}
'''
conf.smtp_hostname = 'mail.dom.lan'
conf.app_dir = '/home/inpos/tmp/serpent'
conf.smtp_queue_dir = 'smtp_queue'
conf.smtp_message_size = 40                 # Размер в МБ
conf.smtp_queue_check_period = 30           # Период запуска обработки очереди в минутах
conf.smtp_queue_message_ttl = 3 * 24 * 60   # Время жизни сообщения в очереди в минутах
conf.maildir_user_path = 'mailstore/%s/'
conf.smtp_email_tls_required = True

conf.imap_SENT = 'Sent'
conf.imap_TRASH = 'Trash'
conf.imap_subscribed = '.subscribed'
conf.imap_flags = 'flags'
conf.imap_auto_mbox = ['INBOX', 'Sent', 'Trash']
conf.imap_expunge_on_close = True
conf.imap_check_new_interval = 10.0         # Период проверки новых сообщений в ящике