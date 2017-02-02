import os
import sys
import psutil
import socket
import logging

from flask import Flask
from flask import jsonify

from waitress import serve

from kimo import conf

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('kimo-server')

app = Flask(__name__)


sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


@app.route("/connections")
def list():
    # TODO:
    # Sepate commann line arguments for kimo-server
    # Add verbose mode.
    net_connections = psutil.net_connections()
    connections = []
    for conn in net_connections:
        process_cmdline = None
        process_name = None
        process_error = None
        if conn.pid:
            try:
                p = psutil.Process(pid=conn.pid)
                process_cmdline = p.cmdline()
                process_name = p.name()
            except Exception:
                process_error = 'ProcessNotFound'
                logger.error('Process not found for  pid: %s', conn.pid)

        connections.append({
            'laddr': conn.laddr,
            'raddr': conn.raddr,
            'status': conn.status,
            'process': {
                'pid': conn.pid,
                'name': process_name,
                'cmdline': process_cmdline,
                'error': process_error,
            }
        })

    return jsonify(connections=connections, hostname=socket.gethostname())


def main():
    app.debug = True
    serve(app, host='0.0.0.0', port=conf.KIMO_SERVER_PORT)
