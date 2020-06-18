"""Module containing all tests for pytest-redis."""
from pytest_redis import factories

def test_redis(redisdb):
    """Check that it's actually working on redis database."""
    redisdb.set('test1', 'test')
    redisdb.set('test2', 'test')

    test1 = redisdb.get('test1')
    assert test1 == b'test'

    test2 = redisdb.get('test2')
    assert test2 == b'test'


def test_second_redis(redisdb, redisdb2):
    """Check that two redis prorcesses are separate ones."""
    redisdb.set('test1', 'test')
    redisdb.set('test2', 'test')
    redisdb2.set('test1', 'test_other')
    redisdb2.set('test2', 'test_other')

    assert redisdb.get('test1') == b'test'
    assert redisdb.get('test2') == b'test'

    assert redisdb2.get('test1') == b'test_other'
    assert redisdb2.get('test2') == b'test_other'


def test_external_redis(redisdb2, redisdb2_noop):
    """Check that nooproc connects to the same redis."""
    redisdb2.set('test1', 'test_other')
    redisdb2.set('test2', 'test_other')

    assert redisdb2.get('test1') == b'test_other'
    assert redisdb2.get('test2') == b'test_other'

    assert redisdb2_noop.get('test1') == b'test_other'
    assert redisdb2_noop.get('test2') == b'test_other'


def test_fixture_default_scope():
    """Check that a default fixture scope is 'function'."""
    redis_my_proc = factories.redis_proc(port=None, logsdir='/tmp')
    redis_my = factories.redisdb('redis_my_proc')

    assert redis_my._pytestfixturefunction.scope == 'function'


def test_fixture_custom_scope():
    """Check that a default fixture scope is 'function'."""
    redis_my_proc = factories.redis_proc(port=None, logsdir='/tmp')
    redis_my = factories.redisdb('redis_my_proc', scope='session')

    assert redis_my._pytestfixturefunction.scope == 'session'
