from __future__ import absolute_import
import logging

import mysql.connector

from .filters import apply_filters
from .process import Process

logger = logging.getLogger(__name__)


def get_process_list(config, filters=[]):
    """
    Get process list from DB and return cleaned&filtered list.
    """
    # Connect to the database
    connection = mysql.connector.connect(host=config['mysql_host'],
                                         user=config['mysql_user'],
                                         password=config['mysql_password'],
                                         db='information_schema')

    rows = []
    try:
        cursor = connection.cursor()
        columns = ','.join(Process._fields)
        cursor.execute('SELECT %s FROM PROCESSLIST' % columns)
        while True:
            row = cursor.fetchone()
            if not row:
                break

            process = Process._make(row)
            rows.append(process)
    finally:
        connection.close()

    logger.debug('Total rows returned from database: %d', len(rows))
    return list(apply_filters(rows, filters))
