dynmc
=====

Dynamically shutdown and restart minecraft servers when empty

How it works
------------

The script emulates the handshake, status, and login of a minecraft server. It will appear to players that the server is online, however, the server is not actually running.

If a player attempts to connect to the server, the script will release control and start the server. At this point, players can connect and play normally. 
The script will continue monitoring the number of players online, and if the server goes long enough without anybody online, it shuts down and the script takes over,
mimicking the server once again.

The process is mostly seamless for the end users, only requiring they connect a second time if they are the one who is initiating the server startup.

Installation
------------

- python >= 3.7

pip libraries:
- `mcrcon == 0.6.0` (0.7.0 will NOT work)

Clone this repository, and place `dynmc.py` somewhere on your path. Alternatively, you can just place it inside of the folder of the minecraft server you want to manage.

Usage
-----

In the root directory of the server (e.g where `server.properties` is stored), run `dynmc.py`. You *MUST* have a `start.sh` file that starts your server, as this is what the script will use.

Ensure the all of the following are true for `server.properties`:
 - `enable-rcon` is set to `true`
 - `rcon.password` is set

Configuration
-------------

For all configuration options, command line arguments will take priority over environment variables.

`--empty-time`, `DYNMC_EMPTY_TIME`
 - Time in seconds before the server is shut down from being empty
 - default: `600` (10 minutes)