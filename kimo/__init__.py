from __future__ import absolute_import
import logging
from Queue import Queue
import threading
from functools import wraps
from collections import namedtuple

import requests

from .mysql import get_process_list
from .process import EnhancedProcess, ProcessDetails
from .cache import Cache
from . import defaults

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def kimo(config, filters=[]):
    """
    Get process ids of MySQL queries.
    """
    process_list = get_process_list(config, filters=filters)
    logger.debug('Total processes from get_process_list: %d', len(process_list))

    q = Queue()
    threads = []
    for process in process_list:
        t = threading.Thread(target=wrapper_find_process_details, args=(process, config, q), name=process.host)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    results = []
    while not q.empty():
        results.append(q.get())

    logger.debug("len(results): %s", len(results))
    return results


def wrapper_find_process_details(process, config, result_queue):
    """
    Wrapper for find_process_details function.

    Add find_process_details results to result_queue.
    """
    parts = process.host.split(':')
    if len(parts) == 1:
        result_queue.put(EnhancedProcess(process=process, details=None))
        return

    host, port = parts
    port = int(port)
    try:
        result = find_process_details(host, port, config)
    except Exception as e:
        exc_type = e.__class__.__name__
        logger.error("cannot get pid: %s: %s", exc_type, e)
        result = e
    result_queue.put(EnhancedProcess(process=process, details=result))


def cache_result(f):
    """
    Thread-safe cache decorator.
    """
    c = Cache()

    @wraps(f)
    def inner(*args, **kwargs):
        return c.get(kwargs.pop('cache_key'), f, *args, **kwargs)
    return inner


class ConnectionNotFound(Exception):
    pass


def find_process_details(host, port, config):
    """
    Find the OS process id of a MySQL query.

    Sample flow is below:

        Client -> tcpproxy -> MySQL

    """
    # mysql shows 127.0.0.1 in processlist output but the real host may look different from outside.
    connect_host = host
    if host in ('127.0.0.1', 'localhost'):
        connect_host = config['mysql_host']

    session = requests.Session()

    data = request_kimo_server(session, connect_host, config, cache_key=connect_host)
    hostname = data['hostname']
    logger.debug("hostname received from kimo-server: %s", hostname)

    conn = find_client_conn_from_kimo_server(data['connections'], port)
    if not conn:
        raise ConnectionNotFound(host, port)

    logger.debug('found conn: %s', conn)
    if conn['name'] == 'tcpproxy':
        logger.debug('Found tcpproxy! Getting connections from tcpproxy.')
        proxy_host = conn['laddr'][0]

        proxy_conns = request_tcpproxy_server(session, proxy_host, config, cache_key=proxy_host)

        # If client is not responding anymore, we should use the above item.
        # This case occurs for example if connection status is TIME_WAIT.
        # If Client does not response, we should use TcpProxy1 for below case;
        # Client -> TcpProxy1 -> TcpProxy2 -> MySQL
        host = find_client_host_from_tcpproxy(proxy_conns, port)
        if host:
            logger.debug("found client in tcpproxy: %s", host)

            # replace 127.0.0.1 with the real IP of the client
            host, port = host.split(':')
            port = int(port)
            if host == '127.0.0.1':
                host = proxy_host

            try:
                return find_process_details(host, port, config)
            except Exception:
                logger.debug('Could not found the connection behind tcpproxy for host: %s port: %s', host, port)

    return ProcessDetails(
            pid=conn['pid'],
            name=conn['name'],
            cmdline=conn['cmdline'],
            connection_status=conn['status'],
            hostname=hostname,
    )


@cache_result
def request_kimo_server(session, connect_host, config, cache_key=None):
    """
    Get kimo server connections from given host.
    """
    kimo_server_url = 'http://' + connect_host + ':' + str(config['kimo_server_port']) + '/connections'
    logger.info('Getting connections from kimo-server at: %s', connect_host)
    response = session.get(kimo_server_url, timeout=(defaults.SERVER_CONNECT_TIMEOUT, defaults.SERVER_READ_TIMEOUT))
    response.raise_for_status()
    return response.json()


@cache_result
def request_tcpproxy_server(session, proxy_host, config, cache_key=None):
    """
    Get connections from tcpproxy from given host.
    """
    logger.info("Getting connections from tcpproxy at: %s", proxy_host)
    tcpproxy_url = 'http://%s:%s/conns' % (proxy_host, config['tcpproxy_mgmt_port'])
    response = session.get(tcpproxy_url, timeout=(defaults.SERVER_CONNECT_TIMEOUT, defaults.SERVER_READ_TIMEOUT))
    response.raise_for_status()

    # Sample Output:
    # 10.0.4.219:36149 -> 10.0.0.68:3306 -> 10.0.0.68:35423 -> 10.0.0.241:3306
    # <client>:<output_port> -> <proxy>:<input_port> -> <proxy>:<output_port>: -> <mysql>:<input_port>
    connection_lines = response.content.split('\n')
    logger.debug('%d lines of tcpproxy output.', len(connection_lines))

    items = []
    TcpProxyConn = namedtuple('TcpProxyConn', 'client_output, proxy_input, proxy_output, mysql_input')
    for line in connection_lines:
        line = line.replace(' ', '')
        if not line:
            continue

        parts = line.split('->')
        if len(parts) != 4:
            logger.error('unexpected output from tcp proxy. parts=%d, line=%q', len(parts), line)
            continue

        items.append(TcpProxyConn._make(parts))
    return items


def find_client_conn_from_kimo_server(connections, client_output_port):
    """
    Find related connection from kimo server.
    """
    assert isinstance(client_output_port, int)
    for conn in connections:
        if client_output_port == conn['laddr'][1]:
            return conn


def find_client_host_from_tcpproxy(conns, tcpproxy_output_port):
    """
    Find related clien host from tcpproxy.
    """
    assert isinstance(tcpproxy_output_port, int)
    for conn in conns:
        thost, tport = conn.proxy_output.split(':')
        tport = int(tport)
        if tport == tcpproxy_output_port:
            return conn.client_output
