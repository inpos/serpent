import asyncio
 
clients = {} # task -> (reader, writer)
 
def client_connected_handler(client_reader, client_writer):
    # Start a new asyncio.Task to handle this specific client connection
    task = asyncio.Task(handle_client(client_reader, client_writer))
    clients[task] = (client_reader, client_writer)
 
    def client_done(task):
        # When the tasks that handles the specific client connection is done
        del clients[task]
 
    # Add the client_done callback to be run when the future becomes done
    task.add_done_callback(client_done)
 
@asyncio.coroutine
def handle_client(client_reader, client_writer):
    # Handle the requests for a specific client with a line oriented protocol
    while True:
        # Read a line
        data = (yield from client_reader.readline())
        # Send it back to the client
        client_writer.write(data)
 
loop = asyncio.get_event_loop()
server = loop.run_until_complete(asyncio.start_server(client_connected_handler, 'localhost', 2222))
try:
    loop.run_forever()
finally:
    loop.close()