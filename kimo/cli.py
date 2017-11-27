import os
import time
import argparse
from ConfigParser import SafeConfigParser

from terminaltables import AsciiTable

from . import kimo, logger
from . import defaults
from .process import Process, ProcessDetails
from .logging import setup_logging


def load_mysql_config(mysql_config_path, config):
    """
    Load MySQL config from configuration file.
    """

    parser = SafeConfigParser()
    try:
        parser.read(mysql_config_path)
    except Exception as e:
        logger.warning("cannot read config from %s: %s", mysql_config_path, e)
        return

    update_config(config, 'mysql_host', parser, 'host')
    update_config(config, 'mysql_port', parser, 'port')
    update_config(config, 'mysql_user', parser, 'user')
    update_config(config, 'mysql_password', parser, 'password')


def update_config(config, config_key, parser, parser_key):
    try:
        config[config_key] = parser.get('client', parser_key)
    except Exception:
        return logger.debug('cannot get client config. key: %s', parser_key)


def main():
    parser = argparse.ArgumentParser(description='Find processes of MySQL queries.')

    parser.add_argument('--logging-level',
                        default='info',
                        choices=['debug', 'info', 'warning', 'error'],
                        type=str.lower,
                        help='Print debug logs')
    parser.add_argument('--host', help='Host of database')
    parser.add_argument('--user', help='User for database')
    parser.add_argument('--password', help='Password for database')
    parser.add_argument('--mysql-config-file', default=defaults.MYSQL_CONFIG_FILE)
    parser.add_argument('--kimo-server-port', type=int, default=defaults.KIMO_SERVER_PORT)
    parser.add_argument('--tcpproxy-mgmt-port', type=int, default=defaults.TCPPROXY_MGMT_PORT)
    parser.add_argument('--filter-query-id', type=int, help='Filter by query ID')
    parser.add_argument('--filter-db', help='Filter by database')
    parser.add_argument('--filter-user', help='Filter by user')
    parser.add_argument('--sort-asc',
                        choices=['db', 'user', 'id', 'host', 'process_host'],
                        type=str.lower,
                        help='Sort output by field in ascending order.')
    parser.add_argument('--sort-desc',
                        choices=['db', 'user', 'id', 'host', 'process_host'],
                        type=str.lower,
                        help='Sort output by field in descending order.')
    parser.add_argument('--output-format', choices=['table', 'vertical'], default='table')

    args = parser.parse_args()

    setup_logging(args.logging_level)

    filters = []
    if args.filter_query_id:
        filters.append(('id', args.filter_query_id))

    if args.filter_db:
        filters.append(('db', args.filter_db))

    if args.filter_user:
        filters.append(('user', args.filter_user))

    # Default sorting field is Query ID
    sort = {'field': 'id', 'reverse': False}
    if args.sort_asc:
        sort = {'field': args.sort_asc, 'reverse': False}

    if args.sort_desc:
        sort = {'field': args.sort_desc, 'reverse': True}

    start_time = time.time()
    processes = kimo(get_config(args), filters=filters)
    total_time = time.time() - start_time
    logger.info('%d rows in set (%.2f sec)', len(processes), total_time)
    print_result(processes, args.output_format, sort=sort)


def get_config(args):
    """
    Get MySQL config via config file or command line.
    """
    config = {
        'mysql_host': '127.0.0.1',
        'mysql_port': 3306,
        'mysql_user': 'root',
        'mysql_password': '',
        'tcpproxy_mgmt_port': args.tcpproxy_mgmt_port,
        'kimo_server_port': args.kimo_server_port,
    }
    if os.path.exists(args.mysql_config_file):
        load_mysql_config(args.mysql_config_file, config)
    if args.host:
        config['mysql_host'] = args.host
    if args.user:
        config['mysql_user'] = args.user
    if args.password:
        config['mysql_password'] = args.password
    return config


def print_result(processes, output_format, sort={'field': 'id', 'reverse': False}):
    """
    Print result in one of 2 forms: Table or Vertical.
    """
    if not processes:
        return

    reverse = sort['reverse']
    attr = sort['field']
    processes.sort(key=lambda x: getattr(x.process, attr), reverse=reverse)

    printers = {
            'table': print_tabular,
            'vertical': print_vertical,
    }
    printers[output_format](processes)


def print_vertical(processes):
    """
    Print with leftpad like MySQL \G mode.

    For example:

         ID: 1234
       Host: worker-1
    Command: python

    """
    headers = Process._fields + ProcessDetails._fields
    max_length = len(max(headers, key=len))

    for i, process in enumerate(processes, 1):
        print('*********************** %s. row ***********************' % i)
        for attr in Process._fields:
            value = getattr(process.process, attr)
            print(attr.rjust(max_length) + ': ' + str(value))

        if process.details is None:
            pass
        elif isinstance(process.details, Exception):
            # TODO
            pass
        elif isinstance(process.details, ProcessDetails):
            for attr in ProcessDetails._fields:
                value = getattr(process.details, attr)
                print(attr.rjust(max_length) + ': ' + str(value))


def print_tabular(processes):
    headers = Process._fields + ProcessDetails._fields
    table_data = [headers]
    for process in processes:
        values = []
        for attr in Process._fields:
            value = getattr(process.process, attr)
            values.append(value)

        if process.details is None:
            pass
        elif isinstance(process.details, Exception):
            # TODO
            pass
        elif isinstance(process.details, ProcessDetails):
            for attr in ProcessDetails._fields:
                value = getattr(process.details, attr)
                values.append(value)

        table_data.append(values)

    table = AsciiTable(table_data)
    print(table.table)
