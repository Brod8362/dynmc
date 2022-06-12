#!/bin/python3
import os
import socket
import ctypes
from ctypes import byref

mclib = ctypes.cdll.LoadLibrary("./mcvars.so")
mclib.read_var_int.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint64)]
mclib.read_var_int.restype = ctypes.c_int32
mclib.read_var_long.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint64)]
mclib.read_var_long.restype = ctypes.c_int64


def main():
    if not os.path.exists("server.properties"):
        print("cannot find server.properties, exiting")
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

    sock = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    )
    sock.bind(("127.0.0.1", SERVER_PORT))
    sock.listen(2)
    while True:
        conn, addr = sock.accept()
        data = conn.recv(1024)
        pos = ctypes.c_ulong(0)
        length = mclib.read_var_int(data, byref(pos))
        print(f"RAWLEN: {len(data)} DLEN: {length} POS:{pos}")
        print(f"{addr}: {data}")

    
if __name__ == "__main__":
    main()