#!/bin/python3
import base64
import os
import socket
import json
import subprocess
from threading import Event, Thread
import time
from mcrcon import MCRcon
"""mcrcon must be version ==0.6.0!"""

SEGMENT_BITS = 0x7F
CONTINUE_BIT = 0x80

def read_var_int(buf: bytes, begin = 0):
    """Read a varint

    Params:
        buf - bytes object
        begin - index to start reading at

    Returns:
        (value, len)
        value - value of the varint
        len - how many bytes were read
    """
    value = 0
    pos = 0
    byte = 0x00
    idx = 0;
    while True:
        byte = buf[begin+idx]
        idx += 1
        value |= (byte & SEGMENT_BITS) << pos
        if ((byte & CONTINUE_BIT) == 0):
            break
        pos += 7;
    return (value, idx)

def to_var_int(value) -> bytes:
    buf = bytearray()
    while True:
        if ((value & ~SEGMENT_BITS) == 0):
            buf.append(value)
            return bytes(buf)
        buf.append((value & SEGMENT_BITS) | CONTINUE_BIT)
        value = value >> 7

def to_packet_str(data: str) -> bytes:
    return to_var_int(len(data)) + data.encode("utf-8")

class ServerMonitor(Thread):
    def __init__(self, event, host: str, port: int, rcon_password: str, delay = 30, limit = 20):
        Thread.__init__(self)
        self.stopped = event
        self.delay = delay
        self.host = host
        self.port = port
        self.limit = limit
        self.password = rcon_password
        self._consecutive = 0

    def run(self):
        while not self.stopped.wait(self.delay):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((self.host, self.port))

            # send handshake packet
            packet = bytearray()
            packet.append(0x00) #packet ID
            packet += to_var_int(500) # protocol version
            packet += to_packet_str(self.host) #host used to connect
            packet.append(self.port & 0xFF) #lo byte of port
            packet.append(self.port >> 8) #hi byte of port
            packet += to_var_int(0x01)
            s.send(to_var_int(len(packet)) + bytes(packet)) #send the packet

            #now, send the request packet
            packet = bytearray()
            packet.append(0x00)
            s.send(to_var_int(len(packet)) + bytes(packet))

            # recv response
            data = s.recv(4096)
            s.close()
            pos = 0
            total_length, read = read_var_int(data, begin = pos)
            pos+=read
            packet_id, read = read_var_int(data, begin = pos)
            pos+=read
            json_length, read = read_var_int(data, begin = pos)
            pos+=read
            json_str = data[pos:].decode("utf-8")
            jsond = json.loads(json_str)
            if jsond['players']['online'] == 0:
                self._consecutive+=1
            else:
                self._consecutive = 0

            if self._consecutive >= self.limit:
                with MCRcon(self.host, self.password) as mcr:
                    resp = mcr.command("/stop")
                    print(resp)

def main():
    if not os.path.exists("server.properties"):
        print("cannot find server.properties, exiting")
        os._exit(1)

    if not os.path.exists("./start.sh"):
        print("cannot find start.sh, exiting")
        os._exit(1)

    server_properties = {}
    with open("server.properties", "r") as fd:
        while True:
            line = fd.readline()
            if not line:
                break
            args = line.strip().split("=")
            if len(args) == 2:
                server_properties
                server_properties[args[0]] = args[1]

    if "server-port" not in server_properties:
        print("server port not specified")
        os._exit(1)

    SERVER_PORT = int(server_properties["server-port"])

    if "rcon.port" not in server_properties:
        print("rcon port not specified")
        os._exit(1)

    RCON_PORT = int(server_properties["rcon.port"])

    if server_properties.get("enable-rcon", "false") == "false":
        print("rcon is not enabled")
        os._exit(1)

    RCON_PASSWORD = server_properties["rcon.password"]

    SERVER_MOTD = server_properties.get("motd", "")

    sock = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    )
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", SERVER_PORT))
    sock.listen(2)
    print("listening for connections...")
    while True:
        conn, addr = sock.accept()
        data = conn.recv(1024)
        pos = 0
        if data[0] == 0xFE:
            print("SLP packet ignored")
            continue
        length, read = read_var_int(data, begin = pos)
        pos += read
        packet_id, read = read_var_int(data, begin = pos);
        pos += read
        protocol_version, read = read_var_int(data, begin = pos);
        pos += read
        if packet_id == 0x00: #handshake packet
            if data[-1] == 0x01: # STATUS
                #build packet here
                response_json = {
                    "version": {
                        "name": "1.19",
                        "protocol": protocol_version,
                    },
                    "players": {
                        "max": 0,
                        "online": 0
                    },
                    "description": {
                        "text": f"{SERVER_MOTD}",
                        "extra": [
                            {
                                "text": "\nServer paused, connect to restart",
                                "bold": True
                            }
                        ]
                    }
                }
                if os.path.exists("server-icon.png"):
                    with open("server-icon.png", "rb") as fd:
                        data = fd.read()
                        b64 = base64.b64encode(data.replace("\n",""))
                        response_json["favicon"] = f"data:image/png;base64,{b64}"
                json_data = json.dumps(response_json)
                packet = bytearray()
                packet.append(0x00) # write packet ID
                packet.extend(to_packet_str(json_data))
                conn.send(to_var_int(len(packet)) + bytes(packet))
                conn.close()
            elif data[-1] == 0x02: # LOGIN
                packet = bytearray()
                packet.append(0x00)
                response_json = {
                    "text": "Server startup will now occur, please wait and reconnect shortly."
                }
                packet += (to_packet_str(json.dumps(response_json)))
                conn.send(to_var_int(len(packet)) + bytes(packet))
                conn.close()
                sock.close()
                #TODO: rcon handle shutting down the server here
                process = subprocess.Popen(["./start.sh"], shell=True) #RUN server
                stop_flag = Event()
                server_monitor = ServerMonitor(stop_flag, "localhost", SERVER_PORT, RCON_PASSWORD, limit = 1)
                server_monitor.start()
                process.wait()
                stop_flag.set()
                #after server shuts down, reopen the socket
                time.sleep(1)
                sock = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM
                )
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", SERVER_PORT))
                sock.listen(2)
        elif packet_id == 0x01: #ping packet
            conn.send(data)
            conn.close()
    
if __name__ == "__main__":
    main()