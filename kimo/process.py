from collections import namedtuple


# Represents rows returned from msyql "SHOW PROCESSLIST" query.
Process = namedtuple('Process', 'id, user, host, db, command, time, state, info')

# Kime finds additional information about the Process.
ProcessDetails = namedtuple('ProcessDetails', 'pid, name, cmdline, hostname, connection_status')

# Union of Process and ProcessDetails types.
EnhancedProcess = namedtuple('EnhancedProcess', 'process, details')
