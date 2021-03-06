"""Tests for distutils.pypirc.pypirc."""
import sys
import os
import unittest2
import tempfile
import shutil

from distutils2.core import PyPIRCCommand
from distutils2.core import Distribution
from distutils2.log import set_threshold
from distutils2.log import WARN

from distutils2.tests import support

PYPIRC = """\
[distutils]

index-servers =
    server1
    server2

[server1]
username:me
password:secret

[server2]
username:meagain
password: secret
realm:acme
repository:http://another.pypi/
"""

PYPIRC_OLD = """\
[server-login]
username:tarek
password:secret
"""

WANTED = """\
[distutils]
index-servers =
    pypi

[pypi]
username:tarek
password:xxx
"""


class PyPIRCCommandTestCase(support.TempdirManager,
                            support.LoggingSilencer,
                            support.EnvironGuard,
                            unittest2.TestCase):

    def setUp(self):
        """Patches the environment."""
        super(PyPIRCCommandTestCase, self).setUp()
        self.tmp_dir = self.mkdtemp()
        os.environ['HOME'] = self.tmp_dir
        self.rc = os.path.join(self.tmp_dir, '.pypirc')
        self.dist = Distribution()

        class command(PyPIRCCommand):
            def __init__(self, dist):
                PyPIRCCommand.__init__(self, dist)
            def initialize_options(self):
                pass
            finalize_options = initialize_options

        self._cmd = command
        self.old_threshold = set_threshold(WARN)

    def tearDown(self):
        """Removes the patch."""
        set_threshold(self.old_threshold)
        super(PyPIRCCommandTestCase, self).tearDown()

    def test_server_registration(self):
        # This test makes sure PyPIRCCommand knows how to:
        # 1. handle several sections in .pypirc
        # 2. handle the old format

        # new format
        self.write_file(self.rc, PYPIRC)
        cmd = self._cmd(self.dist)
        config = cmd._read_pypirc()

        config = config.items()
        config.sort()
        waited = [('password', 'secret'), ('realm', 'pypi'),
                  ('repository', 'http://pypi.python.org/pypi'),
                  ('server', 'server1'), ('username', 'me')]
        self.assertEquals(config, waited)

        # old format
        self.write_file(self.rc, PYPIRC_OLD)
        config = cmd._read_pypirc()
        config = config.items()
        config.sort()
        waited = [('password', 'secret'), ('realm', 'pypi'),
                  ('repository', 'http://pypi.python.org/pypi'),
                  ('server', 'server-login'), ('username', 'tarek')]
        self.assertEquals(config, waited)

    def test_server_empty_registration(self):
        cmd = self._cmd(self.dist)
        rc = cmd._get_rc_file()
        self.assertTrue(not os.path.exists(rc))
        cmd._store_pypirc('tarek', 'xxx')
        self.assertTrue(os.path.exists(rc))
        content = open(rc).read()
        self.assertEquals(content, WANTED)

def test_suite():
    return unittest2.makeSuite(PyPIRCCommandTestCase)

if __name__ == "__main__":
    unittest2.main(defaultTest="test_suite")
