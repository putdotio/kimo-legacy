import os
import sys
import argparse
import socket
import logging

import psutil
from flask import Flask
from flask import jsonify
from waitress import serve

from . import defaults
from .logging import setup_logging

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/connections")
def list():
    net_connections = psutil.net_connections()
    connections = []
    for conn in net_connections:
        name = None
        cmdline = None
        if conn.pid:
            try:
                p = psutil.Process(pid=conn.pid)
                name = p.name()
                cmdline = p.cmdline()
                if cmdline:
                    cmdline = ' '.join(cmdline)
            except Exception:
                pass

        connections.append({
            'laddr': conn.laddr,
            'raddr': conn.raddr,
            'status': conn.status,
            'pid': conn.pid,
            'name': name,
            'cmdline': cmdline,
        })

    return jsonify(connections=connections, hostname=socket.gethostname())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', default=defaults.KIMO_SERVER_PORT)
    parser.add_argument('--logging-level',
                        default='info',
                        choices=['debug', 'info', 'warning', 'error'],
                        type=str.lower,
                        help='Print debug logs')
    args = parser.parse_args()

    setup_logging(args.logging_level)

    if os.geteuid() != 0:
        sys.stderr.write("need to run with root permissions\n")
        sys.exit(1)

    app.debug = True
    serve(app, host='0.0.0.0', port=defaults.KIMO_SERVER_PORT)
