#!/bin/python3
import os
import socket
import json
import subprocess

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

    SERVER_MOTD = server_properties.get("motd", "")

    sock = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    )
    sock.bind(("127.0.0.1", SERVER_PORT))
    sock.listen(2)
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
        print(f"RAWLEN: {len(data)} DLEN: {length} ID:{packet_id} PROTO:{protocol_version}")
        print(f"{addr}: {data}")
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
                subprocess.run(["./start.sh"], shell=True)
        elif packet_id == 0x01: #ping packet
            conn.send(data)
            conn.close()
    
if __name__ == "__main__":
    main()