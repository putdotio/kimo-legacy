import logging
import threading
import Queue
from collections import OrderedDict

import mysql.connector
import requests

from kimo import conf

logger = logging.getLogger()
null_handler = logging.NullHandler()
logger.addHandler(null_handler)


_LOCK = threading.Lock()
HOST_CACHE = {}
CLIENT_CACHE = {}


def get_mysql_processlist(db_conf):
    """
    Get the list of MySQL processes.
    """
    # Connect to the database
    connection = mysql.connector.connect(host=db_conf['host'],
                                         user=db_conf['user'],
                                         password=db_conf['password'],
                                         db='information_schema')

    try:
        cursor = connection.cursor()
        # Create a new record
        cursor.execute('SELECT ID, User, host, db, Command, Time, State, Info FROM PROCESSLIST')
        rows = []
        while True:
            row = cursor.fetchone()
            if not row:
                break

            # OrderedDict is used because, we want to use column nanmes in the same order with the query.
            rows.append(OrderedDict(zip(cursor.column_names, row)))

        logger.debug('Return %s rows.', len(rows))
        # connection is not autocommit by default. So you must commit to save
        # your changes.
        connection.commit()

    finally:
        connection.close()

    return rows


def get_host_cache(host_addr):
    global HOST_CACHE
    host_cache = HOST_CACHE.get(host_addr)

    if not host_cache:
        return None, None

    if HOST_CACHE[host_addr]['error']:
        raise HOST_CACHE[host_addr]['exception']

    return HOST_CACHE[host_addr]['connections'], HOST_CACHE[host_addr]['hostname']


def cache_connections(host_addr, connections, hostname, error=False, exception=None):
    global HOST_CACHE
    HOST_CACHE[host_addr] = {}
    HOST_CACHE[host_addr]['connections'] = connections
    HOST_CACHE[host_addr]['hostname'] = hostname
    HOST_CACHE[host_addr]['error'] = error
    HOST_CACHE[host_addr]['exception'] = exception


def get_connection(host_addr, port_number, connections):
    for conn in connections:
        if host_addr in conn['laddr'][0] and port_number == conn['laddr'][1]:
            break
    else:
        logger.debug('Could not found a connection for host: %s port: %s', host_addr, port_number)
        return None

    return conn


def get_pid(host_addr, port_number):
    """
    Get the process id of the MySQL query.

    Sample flow is below:

        Client -> tcpproxy -> MySQL

    """
    # TODO: Move to decorator.
    conn = None
    connections, hostname = get_host_cache(host_addr)
    if connections:
        conn = get_connection(host_addr, port_number, connections)

    # TODO: Move to another function.
    if not conn:
        kimo_server_host = 'http://' + host_addr + ':' + str(conf.KIMO_SERVER_PORT) + '/connections'
        print 'Requesting kimo server on host:', kimo_server_host
        try:
            logger.info('Connecting to %s', kimo_server_host)
            with requests.Session() as s:
                response = s.get(kimo_server_host, timeout=(3.0, 10))
        except Exception as e:
            logger.error('Could not connect to kimo server on host: %s', host_addr)
            cache_connections(host_addr, connections, hostname, error=True, exception=e)
            raise e

        try:
            response.raise_for_status()
        except Exception as e:
            logger.error('Error when connecting to kimo server on host: %s', host_addr)
            cache_connections(host_addr, connections, hostname, error=True, exception=e)
            raise e

        connections = response.json()['connections']
        hostname = response.json()['hostname']

        cache_connections(host_addr, connections, hostname)

        conn = get_connection(host_addr, port_number, connections)
        if not conn:
            return None

    if conn['process']['name'] == 'tcpproxy':
        logger.debug('Found tcpproxy! Getting connections from tcpproxy.')
        proxy_host = conn['laddr'][0]
        host, port = get_cached_client_information(host_addr, port_number, proxy_host)
        if host is None:
            host, port = get_origin_host(host_addr, port_number, proxy_host)
            cache_client_information(host_addr, port_number, proxy_host, host, port)

        # If client is not responding anymore, we should use the above item.
        # This case occurs for example if connection status is TIME_WAIT.
        # If Client does not response, we should use TcpProxy1 for below case;
        # Client -> TcpProxy1 -> TcpProxy2 -> MySQL
        if host is None:
            print 'Could not found a connection for host: %s port: %s' % (host_addr, port_number)
            process_dict = {}
            process_dict['process'] = conn['process']
            process_dict['host'] = {'host_addr': host_addr, 'hostname': hostname}
            process_dict['connection_status'] = conn['status']
            return process_dict

        process_dict = get_pid(host, port)

        return process_dict

    process_dict = {}
    process_dict['process'] = conn['process']
    process_dict['host'] = {'host_addr': host_addr, 'hostname': hostname}
    process_dict['connection_status'] = conn['status']
    return process_dict


# TODO: Make this a decorator
def cache_client_information(host_addr, port_number, proxy_host, host, port):
    key = str(host_addr) + str(port_number) + str(proxy_host)
    CLIENT_CACHE[key] = {}
    CLIENT_CACHE[key]['host'] = host
    CLIENT_CACHE[key]['port'] = port


# TODO: Make this a decorator.
def get_cached_client_information(host_addr, port_number, proxy_host):
    key = str(host_addr) + str(port_number) + str(proxy_host)
    if CLIENT_CACHE.get(key):
        return CLIENT_CACHE[key]['host'], CLIENT_CACHE[key]['port']

    return None, None


def get_origin_host(host_addr, port_number, proxy_host):
    """
    Request tcp proxy server to get real client information.
    """
    tcpproxy_url = 'http://%s:%s/conns' % (proxy_host, conf.TCPPROXY_MGMT_PORT)
    try:
        with requests.Session() as s:
            response = s.get(tcpproxy_url, timeout=(3, 10))
    except Exception as e:
        logger.error('Could not connect to tcpproxy: host %s', tcpproxy_url)
        raise e

    try:
        response.raise_for_status()
    except Exception as e:
        logger.error('Error when connecting tcpproxy server: %s', tcpproxy_url)
        raise e

    # Sample Output:
    # 10.0.4.219:36149 -> 10.0.0.68:3306 -> 10.0.0.68:35423 -> 10.0.0.241:3306
    # <client>:<output_port> -> <proxy>:<input_port> -> <proxy>:<output_port>: -> <mysql>:<input_port>
    connection_lines = response.content.split('\n')
    logger.debug('%s lines of tcpproxy output.')
    # tcpproxy'de yeni bir endpoint olsun, specific port number verelim.
    for line in connection_lines:
        l = line.replace(' ', '').split('->')
        if len(l) < 3:
            continue

        try:
            tcpproxy_local_host_addr, tcpproxy_local_port = l[2].split(':')
        except ValueError:
            continue

        tcpproxy_local_port = int(tcpproxy_local_port)
        if tcpproxy_local_host_addr == host_addr and tcpproxy_local_port == port_number:
            break
    else:
        return None, None

    client_host_addr, client_port_number = l[0].split(':')
    client_port_number = int(client_port_number)

    return client_host_addr, client_port_number


def apply_filters(l, permitted_keys, requested_filters):
    """
    Apply filters with pre-defined white-listed keys on list of dictionaries.

    >> l = [{'ID': '1234', 'Host': 'worker-1', 'Time': 12}]
    >> permitted_keys = ['ID', 'Host']
    >> requested_filters = ['ID']
    >> apply_filters(l, permitted_keys, requested_filters)

       [{'ID', '1234'}]

    """
    # TODO: Should we raise exception if a non-permitted key is requested ?
    filtered_list = []
    for element in l:
        matched = True
        for key in permitted_keys:
            if requested_filters.get(key) and requested_filters.get(key) != str(element.get(key)):
                matched = False
                break

        if matched:
            filtered_list.append(element)

    return filtered_list


def get_process_list(db_conf, filters=None):
    """
    Get process list from DB and return cleaned&filtered list.
    """
    process_list = get_mysql_processlist(db_conf)
    process_list = filter(lambda x: x['host'] != 'localhost', process_list)
    if not filters:
        return process_list

    # ID, User, host and db columns are allowed to filter.
    allowed_columns = ['ID', 'User', 'db']
    filtered_list = apply_filters(process_list, allowed_columns, filters)

    return filtered_list


def get_pids(db_conf, filters=None):
    """
    Get process ids of MySQL queries.
    """
    process_list = get_process_list(db_conf, filters=filters)

    def wrapper_get_pid(*args, **kwargs):
        with _LOCK:
            try:
                process_dict = get_pid(*args, **kwargs)
                q.put(process_dict)
            except Exception as e:
                q.put({'error': True, 'exception_name': e.__class__.__name__})

    q = Queue.Queue()
    threads = []
    for row in process_list:
        host, port = row['host'].split(':')
        port = int(port)
        t = threading.Thread(target=wrapper_get_pid, args=(host, port))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    results = []
    while not q.empty():
        results.append(q.get())

    combined_result = []
    for idx, result_process_dict in enumerate(results):
        print 'PROCESS DICT:', result_process_dict
        # Queue returns thread results in same order with the given list.
        db_process_dict = process_list[idx]

        if not result_process_dict:
            continue

        if result_process_dict.get('error'):
            process_cmdline = result_process_dict['exception_name']
            process_pid = result_process_dict['exception_name']
            process_hostname = result_process_dict['exception_name']
            continue

        process_cmdline = None
        process_pid = None
        process_hostname = None
        if result_process_dict['process']['cmdline']:
            process_cmdline = ' '.join(result_process_dict['process']['cmdline'])
        process_pid = result_process_dict['process']['pid']
        process_hostname = result_process_dict['host']['hostname']
        process_name = result_process_dict['process']['name']
        process_conn_status = result_process_dict['connection_status']

        db_process_dict.update({
                'Process_id': process_pid,
                'Process_host': process_hostname,
                'Process_cmdline': process_cmdline,
                'Process_name': process_name,
                'Connection_status': process_conn_status,
        })
        combined_result.append(db_process_dict)

    return combined_result
