#!/bin/python3
import argparse
import base64
from datetime import datetime
import json
import math
import os
import socket
import subprocess
import time
from threading import Event, Thread

from mcrcon import MCRcon
"""mcrcon must be version ==0.6.0!"""


SEGMENT_BITS = 0x7F
CONTINUE_BIT = 0x80

class InvalidVarInt(Exception):
    pass

def log(msg: str):
    time = datetime.now()
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [dynmc]: {msg}")

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
        if (begin+idx >= len(buf)):
            raise InvalidVarInt("ran out of bytes to read")
        byte = buf[begin+idx]
        idx += 1
        value |= (byte & SEGMENT_BITS) << pos
        if ((byte & CONTINUE_BIT) == 0):
            break
        pos += 7;
        if (pos >= 32):
            raise InvalidVarInt("too long")
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
    def __init__(self, event, host: str, port: int, rcon_password: str, time: int = 600, rcon_port: int = 25575):
        Thread.__init__(self)
        self.stopped = event
        self.host = host
        self.port = port
        self.limit = math.ceil(time/30)
        self.password = rcon_password
        self._consecutive = 0
        self.rcon_port = rcon_port

    def run(self):
        while not self.stopped.wait(30):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            try:
                s.connect((self.host, self.port))
            except:
                continue

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
            online = jsond['players']['online']
            if online == 0:
                self._consecutive+=1
            else:
                self._consecutive = 0

            if self._consecutive >= self.limit and online == 0:
                with MCRcon(self.host, self.password, port = self.rcon_port) as mcr:
                    log(f"Server has been empty for {self.limit*30} seconds, shutting down")
                    resp = mcr.command("stop")
                    log(resp)

def main():
    EMPTY_TIME = 600
    if "DYNMC_EMPTY_TIME" in os.environ:
        EMPTY_TIME = int(os.environ["DYNMC_EMPTY_TIME"])
    argp = argparse.ArgumentParser(description="dynamic minecraft server manager")
    argp.add_argument("--empty-time", dest="emptytime", type=int, default=EMPTY_TIME)
    cliargs = argp.parse_args()

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

    BIND_ADDRESS = server_properties.get("server-ip", "0.0.0.0")
    SERVER_PORT = int(server_properties["server-port"])

    if "rcon.port" not in server_properties:
        print("rcon port not specified")
        os._exit(1)

    RCON_PORT = int(server_properties["rcon.port"])

    if server_properties.get("enable-rcon", "false") == "false":
        print("rcon is not enabled")
        os._exit(1)

    log(f"Server will shut down if empty for {cliargs.emptytime} seconds")

    RCON_PASSWORD = server_properties["rcon.password"]

    SERVER_MOTD = server_properties.get("motd", "")

    sock = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    )
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((BIND_ADDRESS, SERVER_PORT))
    sock.listen(2)
    log(f"Listening for connections on {BIND_ADDRESS}:{SERVER_PORT}")
    while True:
        try:
            conn, addr = sock.accept()
            data = conn.recv(1024)
        except Exception as e:
            log(f"Failed to connect with {addr}: {e}")
            continue
        pos = 0
        try:
            length, read = read_var_int(data, begin = pos)
            pos += read
            packet_id, read = read_var_int(data, begin = pos);
            pos += read
            protocol_version, read = read_var_int(data, begin = pos);
            pos += read
        except InvalidVarInt as e:
            log(f"Received invalid packet")
            continue
        except Exception as e:
            log(f"Unhandled exception: {e}")
            continue
        if packet_id == 0x00: #handshake packet
            if data[-1] == 0x01: # STATUS
                #build packet here
                log(f"Sending server status to {addr}")
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
                log(f"{addr} initiated server startup")
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
                server_monitor = ServerMonitor(stop_flag, BIND_ADDRESS, SERVER_PORT, RCON_PASSWORD, time = cliargs.emptytime, rcon_port = RCON_PORT)
                server_monitor.start()
                log("Monitoring server player status")
                process.wait()
                stop_flag.set()
                #after server shuts down, reopen the socket
                time.sleep(1)
                log("Reclaiming control and listening for new connections")
                sock = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM
                )
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((BIND_ADDRESS, SERVER_PORT))
                sock.listen(2)
        elif packet_id == 0x01: #ping packet
            conn.send(data)
            conn.close()
    
if __name__ == "__main__":
    main()
