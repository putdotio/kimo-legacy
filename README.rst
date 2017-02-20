kimo
====

``kimo`` (means *who is it* in Turkish) is a tool for finding OS processes of MySQL queries.

Installation
------------

::

 pip install kimo

Usage
-----

``kimo`` is consisted of two parts: ``kimo-server`` and ``kimo client``.


**Server-Side**


First, we need to run ``kimo-server`` on each server that makes MySQL queries. We need to do this because ``kimo-server`` gets connections from the host that ``kimo-server`` runs on it and provides connections to client via HTTP API.

::

  sudo kimo-server

**Client-Side**

``kimo`` client can be used via command line or inside python program.

**Command Line**

There are some optional arguments for command line interface:


::

  optional arguments:
  -h, --help            show this help message and exit
  --logging-level {debug,info,warning,error}
                        Print debug logs
  --host HOST           Host of database
  --user USER           User for database
  --password PASSWORD   Password for database
  --mysql-config-file MYSQL_CONFIG_FILE
  --kimo-server-port KIMO_SERVER_PORT
  --tcpproxy-mgmt-port TCPPROXY_MGMT_PORT
  --filter-query-id FILTER_QUERY_ID
                        Filter by query ID
  --filter-db FILTER_DB
                        Filter by database
  --filter-user FILTER_USER
                        Filter by user
  --sort-asc {db,user,id,host,process_host}
                        Sort output by field in ascending order.
  --sort-desc {db,user,id,host,process_host}
                        Sort output by field in descending order.
  --output-format {table,vertical}


**Python Program**

::

  from kimo import kimo

  config = {
      'mysql_host': '127.0.0.1',
      'mysql_port': 3306,
      'mysql_user': 'root',
      'mysql_password': '',
      'tcpproxy_mgmt_port': 3307,
      'kimo_server_port': 6000,
  }
  result = kimo(config)
  print result[0]
  
  >>  EnhancedProcess(process=Process(id=1504, user=u'root', host=u'127.0.0.1:54553', db=u'information_schema', command=u'Query', time=547, state=u'User sleep', info=u'select sleep(100)'), details=ProcessDetails(pid=16430, name=u'python', cmdline=u'python -m putio.shell', hostname=u'vagrant.putio.club', connection_status=u'ESTABLISHED'))

That's it!

**TcpProxy**

``kimo`` also works well if there is one or multiple `tcpproxy <https://github.com/cenkalti/tcpproxy>`_ proxy servers between MySQL and clients.

Example
-------

*Server-Side*

First, we must start ``kimo-server``:

::

  sudo kimo-server --logging-level DEBUG --port 6000


*Client-Side*

We can get the output in vertical or table format.

Vertical Output:

::

  kimo  --output-format vertical --filter-query-id 1001

::

  [2017-02-19 19:37:11,817] Thread(127.0.0.1:50212) INFO kimo:request_kimo_server:147 - Getting connections from kimo-server at: 127.0.0.1
  [2017-02-19 19:37:11,900] Thread(MainThread) INFO kimo:main:87 - 1 rows in set (0.09 sec)
  *********************** 1. row ***********************
                 id: 1001
               user: root
               host: 127.0.0.1:50212
                 db: information_schema
            command: Query
               time: 165
              state: User sleep
               info: SELECT SLEEP(500)
                pid: 4796
               name: python
            cmdline: python -m putio.shell
           hostname: vagrant.putio.club
  connection_status: ESTABLISHED


Table Output:

::

  kimo  --output-format table --sort-asc id
 
::

  +------+------+-----------------+--------------------+---------+------+------------+-------------------+------+--------+-----------------------+--------------------+-------------------+
  | id   | user | host            | db                 | command | time | state      | info              | pid  | name   | cmdline               | hostname           | connection_status |
  +------+------+-----------------+--------------------+---------+------+------------+-------------------+------+--------+-----------------------+--------------------+-------------------+
  | 1202 | root | 127.0.0.1:54668 | information_schema | Query   | 18   | User sleep | select sleep(800) | 4796 | python | python -m putio.shell | vagrant.putio.club | ESTABLISHED       |
  +------+------+-----------------+--------------------+---------+------+------------+-------------------+------+--------+-----------------------+--------------------+-------------------+
  | 1207 | root | 127.0.0.1:54593 | information_schema | Query   | 46   | User sleep | select sleep(1000) | 13630 | python | python -m putio.shell | vagrant.putio.club | ESTABLISHED       |
  +------+------+-----------------+--------------------+---------+------+------------+--------------------+-------+--------+-----------------------+--------------------+-------------------+
