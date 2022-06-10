#!/bin/python3
import os

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

    if not server_properties.get("rcon.port", ""):
        print("rcon port not specified")
        os._exit(1)

    if not server_properties.get("enable-rcon", "false") == "true":
        print("rcon is not enabled")
        os._exit(1)

    

if __name__ == "__main__":
    main()