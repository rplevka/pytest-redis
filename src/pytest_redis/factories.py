# Copyright (C) 2013 by Clearcode <http://clearcode.cc>
# and associates (see AUTHORS).

# This file is part of pytest-redis.

# pytest-redis is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# pytest-redis is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with pytest-redis.  If not, see <http://www.gnu.org/licenses/>.
"""FIxture factories for pytest-redis."""
import os
import re
from tempfile import gettempdir

import pytest
import redis
from path import Path
from mirakuru import TCPExecutor

from pytest_redis.port import get_port

REQUIRED_VERSION = '2.6'
"""
Minimum required version of redis that is accepted by pytest-redis.
"""


def get_config(request):
    """Return a dictionary with config options."""
    config = {}
    options = [
        'logsdir'
    ]
    for option in options:
        option_name = 'redis_' + option
        conf = request.config.getoption(option_name) or \
            request.config.getini(option_name)
        config[option] = conf
    return config


class RedisUnsupported(Exception):
    """Exception raised when redis<2.6 would be detected."""

    pass


def compare_version(version1, version2):
    """
    Compare two version numbers.

    :param str version1: first version to compare
    :param str version2: second version to compare
    :rtype: int
    :returns: return value is negative if version1 < version2,
        zero if version1 == version2
        and strictly positive if version1 > version2
    """
    def normalize(v):
        return [int(x) for x in re.sub(r'(\.0+)*$', '', v).split(".")]

    def cmp_v(v1, v2):
        return (v1 > v2) - (v1 < v2)
    return cmp_v(normalize(version1), normalize(version2))


def extract_version(text):
    """
    Extract version number from the text.

    :param str text: text that contains the version number
    :rtype: str
    :returns: version number, e.g., "2.4.14"
    """
    match_object = re.search('\d+(?:\.\d+)+', text)
    if match_object:
        extracted_version = match_object.group(0)
    else:
        extracted_version = None
    return extracted_version


__all__ = ('redisdb', 'redis_proc')


def redis_proc(executable=None, params=None, config_file=None,
               host=None, port=-1, logsdir=None, logs_prefix=''):
    """
    Fixture factory for pytest-redis.

    :param str executable: path to redis-server
    :param str params: params
    :param str config_file: path to config file
    :param str host: hostname
    :param str|int|tuple|set|list port:
        exact port (e.g. '8000', 8000)
        randomly selected port (None) - any random available port
        [(2000,3000)] or (2000,3000) - random available port from a given range
        [{4002,4003}] or {4002,4003} - random of 4002 or 4003 ports
        [(2000,3000), {4002,4003}] -random of given orange and set
    :param str logsdir: path to log directory
    :param str logs_prefix: prefix for log filename
    :rtype: func
    :returns: function which makes a redis process
    """
    @pytest.fixture(scope='session')
    def redis_proc_fixture(request):
        """
        Fixture for pytest-redis.

        #. Get configs.
        #. Run redis process.
        #. Stop redis process after tests.

        :param FixtureRequest request: fixture request object
        :rtype: pytest_redis.executors.TCPExecutor
        :returns: tcp executor
        """
        config = get_config(request)
        redis_exec = executable or '/usr/bin/redis-server'  # TODO
        redis_params = params or ''  # TODO
        # TODO - change into options
        redis_conf = config_file or \
            Path(__file__).parent.abspath() / 'redis.conf'
        redis_host = host or '127.0.0.1'  # TODO
        redis_port = get_port(port) or get_port(6380)  # TODO

        pidfile = 'redis-server.{port}.pid'.format(port=redis_port)
        unixsocket = 'redis.{port}.sock'.format(port=redis_port)
        dbfilename = 'dump.{port}.rdb'.format(port=redis_port)
        redis_logsdir = Path(logsdir or config['logsdir'])
        logfile_path = redis_logsdir / \
            '{prefix}redis-server.{port}.log'.format(
                prefix=logs_prefix,
                port=redis_port
            )

        redis_executor = TCPExecutor(
            '''{redis_exec} {config}
            --pidfile {pidfile} --unixsocket {unixsocket}
            --dbfilename {dbfilename} --logfile {logfile_path}
            --port {port} --dir {tmpdir} {params}'''
            .format(
                redis_exec=redis_exec,
                params=redis_params,
                config=redis_conf,
                pidfile=pidfile,
                unixsocket=unixsocket,
                dbfilename=dbfilename,
                logfile_path=logfile_path,
                port=redis_port,
                tmpdir=gettempdir(),
            ),
            host=redis_host,
            port=redis_port,
            timeout=60,
        )
        redis_version = extract_version(
            os.popen('{0} --version'.format(redis_exec)).read()
        )
        cv_result = compare_version(redis_version, REQUIRED_VERSION)
        if redis_version and cv_result < 0:
            raise RedisUnsupported(
                'Your version of Redis is not supported. '
                'Consider updating to Redis {0} at least. '
                'The currently installed version of Redis: {1}.'
                .format(REQUIRED_VERSION, redis_version))
        redis_executor.start()
        request.addfinalizer(redis_executor.stop)

        return redis_executor

    return redis_proc_fixture


def redisdb(process_fixture_name, db=None, strict=True):
    """
    Connection fixture factory for pytest-redis.

    :param str process_fixture_name: name of the process fixture
    :param int db: number of database
    :param bool strict: if true, uses StrictRedis client class
    :rtype: func
    :returns: function which makes a connection to redis
    """
    @pytest.fixture
    def redisdb_factory(request):
        """
        Connection fixture for pytest-redis.

        #. Load required process fixture.
        #. Get redis module and config.
        #. Connect to redis.
        #. Flush database after tests.

        :param FixtureRequest request: fixture request object
        :rtype: redis.client.Redis
        :returns: Redis client
        """
        proc_fixture = request.getfuncargvalue(process_fixture_name)

        redis_host = proc_fixture.host
        redis_port = proc_fixture.port
        redis_db = db or 0  # TODO
        redis_class = redis.StrictRedis if strict else redis.Redis

        redis_client = redis_class(
            redis_host, redis_port, redis_db, decode_responses=True)
        request.addfinalizer(redis_client.flushall)

        return redis_client

    return redisdb_factory