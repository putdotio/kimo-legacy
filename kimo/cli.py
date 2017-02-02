import os
import sys
import time
import logging
import argparse
from ConfigParser import SafeConfigParser

from terminaltables import AsciiTable

from kimo import get_pids
from kimo import apply_filters

logger = logging.getLogger('kimo')
logger.setLevel(logging.INFO)

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


def load_config():
    """
    Load MySQL config from configuration file.
    """
    config = SafeConfigParser()
    config.read('/etc/mysql/my.cnf')
    return {
            'user': config.get('client', 'user'),
            'host': config.get('client', 'host'),
            'password': config.get('client', 'password'),
    }


def main():
    # TODO:
    # Stop all running threads with Keyboard Interrupt
    # Verbose mode for debug logs.
    # Cache latest result on local disk.

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Find the process ids of a MySQL queries.')

    parser.add_argument('--host',
                        dest='host',
                        type=str,
                        help='Host of database')
    parser.add_argument('--user',
                        dest='user',
                        type=str,
                        help='User for database')
    parser.add_argument('--password',
                        dest='password',
                        type=str,
                        help='Password for database')
    parser.add_argument('--filter-id',
                        dest='filter_id',
                        type=str,
                        help='Filter by ID')
    parser.add_argument('--filter-db',
                        dest='filter_db',
                        type=str,
                        help='Filter by db')
    parser.add_argument('--filter-user',
                        dest='filter_user',
                        type=str,
                        help='Filter by User')
    parser.add_argument('--filter-process_host',
                        dest='filter_process_host',
                        type=str,
                        help='Filter by process host')
    parser.add_argument('--fields',
                        dest='fields',
                        type=str,
                        help='Comma seperated list of column fields.')
    parser.add_argument('--vertical_output',
                        action='store_true',
                        default=False,
                        help='Vertical output like \G for MySQL')

    args = parser.parse_args()

    db_filters = {
            'ID': args.filter_id or None,
            'db': args.filter_db or None,
            'User': args.filter_user or None
    }
    result_filters = {
            'Process_host': args.filter_process_host or None,
    }

    allowed_fields = [
            'ID',
            'User',
            'db',
            'Process_id',
            'Process_host',
            'Process_cmdline',
            'Connection_status']
    fields = None
    if args.fields:
        fields = args.fields.split(',')
        for f in fields:
            if f not in allowed_fields:
                argparse.ArgumentError(fields,
                                       'fields must be one of %s' % allowed_fields)

    db_conf = {}
    if all([args.host, args.user, args.password]):
        # TODO: User must specify all or none of these.
        db_conf['host'] = args.host or 'localhost'
        db_conf['user'] = args.user or ''
        db_conf['password'] = args.password or ''
    else:
        db_conf = load_config()

    vertical_output = args.vertical_output or False

    start_time = time.time()
    result = get_pids(db_conf, filters=db_filters)
    print_result(result, start_time, filters=result_filters, fields=fields, vertical_print=vertical_output)


def print_result(result, start_time, filters=None, fields=None, vertical_print=False):
    """
    Print the result in a tabular form.
    """
    if len(result) == 0:
        # TODO: Get rid of no-result cases.
        print 'No result!'
        return

    if filters:
        # Process_host is allowed for filtering.
        allowed_columns = ['Process_host', ]
        result = apply_filters(result, allowed_columns, filters)

    filtered_fields = []
    if fields:
        for column in result[0].keys():
            if column in fields:
                filtered_fields.append(column)
    else:
        filtered_fields = result[0].keys()

    if vertical_print:
        print_vertical(result, filtered_fields)
    else:
        print_tabular(result, filtered_fields)

    total_time = time.time() - start_time
    print '%d rows in set (%.2f sec)' % (len(result), total_time)


def print_vertical(result, fields):
    """
    Print with leftpad like MySQL \G mode.

    For example:

         ID: 1234
       Host: worker-1
    Command: python

    """
    max_length = len(max(fields, key=len))

    for idx, r in enumerate(result, 1):
        print '*********************** %s. row ***********************' % idx
        for key, value in r.iteritems():
            print key.rjust(max_length) + ': ' + str(value)


def print_tabular(result, fields):
    # The header is in order with the result order.
    table_data = [
            fields
    ]

    # TODO:
    # Info rowlar icin max 50 karakter gosterelim.
    # Bir flagle bunu CLI ile de manuel ayarlayabilelim.
    # sqlparse ise column isimlerini collapse edip SELECT, FROM, JOIN, WHERE vs. gibi
    # onemli seyletri gostertelim: https://pypi.python.org/pypi/sqlparse
    for r in result:
        l = []
        for key, value in r.iteritems():
            if key in fields:
                l.append(value)
        table_data.append(l)

    table = AsciiTable(table_data)
    print table.table

if __name__ == '__main__':
    main()
