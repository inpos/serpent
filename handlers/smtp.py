from socketserver import StreamRequestHandler

ERR_CODE = {
            220 : ''
            500 : 'Syntax error, command unrecognized',
            }

class SmtpProcessor(object):
    def __init__(self, src_addr, rfile,wfile):
        self.src_addr = src_addr
        self.rfile = rfile
        self.wfile = wfile
        self.unrec_commands_count = 0

class SmtpHandler(StreamRequestHandler):

    def handle(self):
        # self.rfile is a file-like object created by the handler;
        # we can now use e.g. readline() instead of raw recv() calls
        self.data = self.rfile.readline().strip()
        print("{} wrote:".format(self.client_address[0]))
        print(self.data)
        # Likewise, self.wfile is a file-like object used to write back
        # to the client
        self.wfile.write(self.data.upper())
        
        #######################################################
        processor = SmtpProcessor(self.client_address, self.rfile, self.wfile)
        