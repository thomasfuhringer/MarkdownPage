# Server for Markdown Pages
# Thomas Führinger, 2022-06-07, github.com/thomasfuhringer/markdownpage

"""
Protocol:

bytes
 4	message length
 2	identifier (0x06, 0x0E)
 1	message type (unused)
 4	page length
 n	page (zipped)
 2	path length
 n	path
 2	number of subpages
 2	length of subpage name 1
 n	subpage name 1
 2	length of subpage name 2
 n	subpage name 2
 """

import socket, threading, time, zipfile, io, os

default_host = "localhost"
default_port = 1550
identifier = bytes([0x06, 0x0E])

class MessageType:
    Query = b'0x00',
    ShutDown = b'0xFF'

def JDN(gregorian):
    """Convert the given proleptic Gregorian date to the equivalent Julian Day Number."""
    A = int((gregorian.month - 14) / 12)
    B = 1461 * (gregorian.year + 4800 + A)
    C = 367 * (gregorian.month - 2 - 12 * A)
    E = int((gregorian.year + 4900 + A) / 100)
    return int(B / 4) + int(C / 12) - int(3 * E / 4) + gregorian.day - 32075

def JSN(gregorian): # Julian Second Number
    return JDN(gregorian) * 1440 + (gregorian.hour * 60) + gregorian.second

class Server(object):
    backlog = 5

    def __init__(self, host=default_host, port=default_port):
        self.sessions = []
        self.socket = socket.socket()
        self.socket.bind((host, port))
        self.socket.listen(Server.backlog)
        self.up = True
        self.path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "Site")
        print("Markdown Page server running on host '{}', port {}.".format(host, port))

    def run(self):

        while self.up:
            (clientsocket, address) = self.socket.accept()
            session = Session(clientsocket, address, self)
            self.sessions += [session]
            session.start()
            time.sleep(1)

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except Exception as e:
            pass

        print("Server halted.")


class Session(threading.Thread):
    def __init__(self, socket, address, server):
        threading.Thread.__init__(self)
        self.socket = socket
        self.address = address
        self.server = server
        #self.up = True

    def send(self, data):
        length = len(data)
        self.socket.send(length.to_bytes(4, byteorder="big"))
        self.socket.sendall(data)

    def receive(self):
        length_bytes = self.socket.recv(4)
        if len(length_bytes) != 4:
            return None

        length = int.from_bytes(length_bytes, byteorder="big")
        data = bytearray(length)
        view = memoryview(data)
        next_offset = 0
        while length - next_offset > 0:
            recv_size = self.socket.recv_into(view[next_offset:], length - next_offset)
            if recv_size == 0:
                return None
            next_offset += recv_size
        return data

    def run(self):
        query = self.receive()
        if len(query) < 3 or query[:2] != identifier:
            print("Invalid connection request from address: " + self.address[0] + ", port: " + str(self.address[1]))
            self.socket.close()
            return

        if query[2:3] == MessageType.ShutDown:
            self.server.up = False
            self.socket.close()
            return

        page = self.construct_page(query[5:])

        self.send(bytes([0x06, 0x0E, 255]) + page)
        self.socket.close()

    def construct_page(self, path):
        file_path = self.server.path
        found = False
        path_elements = []
        if path == b"":
            found = True
        else:
            path_list = path.decode().split("/")
            for directory in path_list:
                if directory == "":
                    continue
                found = False
                with os.scandir(file_path) as iterator:
                    for entry in iterator:
                        if entry.is_dir() and entry.name == directory:
                            file_path = os.path.join(file_path, entry.name)
                            path_elements.append(entry.name)
                            found = True
                            break
                if not found:
                    with os.scandir(file_path) as iterator:
                        for entry in iterator:
                            if entry.is_dir() and entry.name.casefold() == directory.casefold():  # Make lookup path case insensitive
                                file_path = os.path.join(file_path, entry.name)
                                path_elements.append(entry.name)
                                found = True
                                break
                if not found:
                    path_elements.append(directory)
                    break

        if not found:
            path_bytes = bytes("/".join(path_elements), "utf-8")
            return b"4" + len(path_bytes).to_bytes(2, byteorder="big") + path_bytes

        page = io.BytesIO()
        subpages = b""
        subpages_count = 0
        with zipfile.ZipFile(page, "a", zipfile.ZIP_DEFLATED) as zip_file:
            with os.scandir(file_path) as iterator:
                for entry in iterator:
                    if entry.is_file():
                        zip_file.write(os.path.join(file_path, entry.name), entry.name)
                    if entry.is_dir():
                        entry_bytes = bytes(entry.name, "utf-8")
                        subpages += len(entry_bytes).to_bytes(2, byteorder="big") + entry_bytes + bytes([0, 0, 0, 0]) # last 4 bytes placeholder for time stamp in Julian minutes
                        subpages_count += 1
        page_str = page.getvalue()
        path_bytes = bytes("/".join(path_elements), "utf-8")
        return b"0" + len(page_str).to_bytes(4, byteorder="big") + page_str + len(path_bytes).to_bytes(2, byteorder="big") + path_bytes + subpages_count.to_bytes(2, byteorder="big") + subpages

server = Server()
# server = Server("45.76.133.182")
server.run()