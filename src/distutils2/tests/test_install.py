"""Tests for distutils.command.install."""

import os
import os.path
import sys
import unittest2
import site

from distutils2._backport import sysconfig
from distutils2._backport.sysconfig import (get_scheme_names,
                                            get_config_vars,
                                            _SCHEMES,
                                            get_config_var, get_path)

_CONFIG_VARS = get_config_vars()

from distutils2.tests import captured_stdout

from distutils2.command.install import install
from distutils2.command import install as install_module
from distutils2.core import Distribution
from distutils2.errors import DistutilsOptionError

from distutils2.tests import support

class InstallTestCase(support.TempdirManager,
                      support.EnvironGuard,
                      support.LoggingSilencer,
                      unittest2.TestCase):

    def test_home_installation_scheme(self):
        # This ensure two things:
        # - that --home generates the desired set of directory names
        # - test --home is supported on all platforms
        builddir = self.mkdtemp()
        destination = os.path.join(builddir, "installation")

        dist = Distribution({"name": "foopkg"})
        # script_name need not exist, it just need to be initialized
        dist.script_name = os.path.join(builddir, "setup.py")
        dist.command_obj["build"] = support.DummyCommand(
            build_base=builddir,
            build_lib=os.path.join(builddir, "lib"),
            )

        old_posix_prefix = _SCHEMES.get('posix_prefix', 'platinclude')
        old_posix_home = _SCHEMES.get('posix_home', 'platinclude')

        new_path = '{platbase}/include/python{py_version_short}'
        _SCHEMES.set('posix_prefix', 'platinclude', new_path)
        _SCHEMES.set('posix_home', 'platinclude', '{platbase}/include/python')

        try:
            cmd = install(dist)
            cmd.home = destination
            cmd.ensure_finalized()
        finally:
            _SCHEMES.set('posix_prefix', 'platinclude', old_posix_prefix)
            _SCHEMES.set('posix_home', 'platinclude', old_posix_home)

        self.assertEqual(cmd.install_base, destination)
        self.assertEqual(cmd.install_platbase, destination)

        def check_path(got, expected):
            got = os.path.normpath(got)
            expected = os.path.normpath(expected)
            self.assertEqual(got, expected)

        libdir = os.path.join(destination, "lib", "python")
        check_path(cmd.install_lib, libdir)
        check_path(cmd.install_platlib, libdir)
        check_path(cmd.install_purelib, libdir)
        check_path(cmd.install_headers,
                   os.path.join(destination, "include", "python", "foopkg"))
        check_path(cmd.install_scripts, os.path.join(destination, "bin"))
        check_path(cmd.install_data, destination)

    def test_user_site(self):
        # site.USER_SITE was introduced in 2.6
        if sys.version < '2.6':
            return

        # preparing the environment for the test
        self.old_user_base = get_config_var('userbase')
        self.old_user_site = get_path('purelib', '%s_user' % os.name)
        self.tmpdir = self.mkdtemp()
        self.user_base = os.path.join(self.tmpdir, 'B')
        self.user_site = os.path.join(self.tmpdir, 'S')
        _CONFIG_VARS['userbase'] = self.user_base
        scheme = '%s_user' % os.name
        _SCHEMES.set(scheme, 'purelib', self.user_site)
        def _expanduser(path):
            if path[0] == '~':
                path = os.path.normpath(self.tmpdir) + path[1:]
            return path
        self.old_expand = os.path.expanduser
        os.path.expanduser = _expanduser

        try:
            # this is the actual test
            self._test_user_site()
        finally:
            _CONFIG_VARS['userbase'] = self.old_user_base
            _SCHEMES.set(scheme, 'purelib', self.old_user_site)
            os.path.expanduser = self.old_expand

    def _test_user_site(self):
        schemes = get_scheme_names()
        for key in ('nt_user', 'posix_user', 'os2_home'):
            self.assertTrue(key in schemes)

        dist = Distribution({'name': 'xx'})
        cmd = install(dist)
        # making sure the user option is there
        options = [name for name, short, lable in
                   cmd.user_options]
        self.assertTrue('user' in options)

        # setting a value
        cmd.user = 1

        # user base and site shouldn't be created yet
        self.assertTrue(not os.path.exists(self.user_base))
        self.assertTrue(not os.path.exists(self.user_site))

        # let's run finalize
        cmd.ensure_finalized()

        # now they should
        self.assertTrue(os.path.exists(self.user_base))
        self.assertTrue(os.path.exists(self.user_site))

        self.assertTrue('userbase' in cmd.config_vars)
        self.assertTrue('usersite' in cmd.config_vars)

    def test_handle_extra_path(self):
        dist = Distribution({'name': 'xx', 'extra_path': 'path,dirs'})
        cmd = install(dist)

        # two elements
        cmd.handle_extra_path()
        self.assertEquals(cmd.extra_path, ['path', 'dirs'])
        self.assertEquals(cmd.extra_dirs, 'dirs')
        self.assertEquals(cmd.path_file, 'path')

        # one element
        cmd.extra_path = ['path']
        cmd.handle_extra_path()
        self.assertEquals(cmd.extra_path, ['path'])
        self.assertEquals(cmd.extra_dirs, 'path')
        self.assertEquals(cmd.path_file, 'path')

        # none
        dist.extra_path = cmd.extra_path = None
        cmd.handle_extra_path()
        self.assertEquals(cmd.extra_path, None)
        self.assertEquals(cmd.extra_dirs, '')
        self.assertEquals(cmd.path_file, None)

        # three elements (no way !)
        cmd.extra_path = 'path,dirs,again'
        self.assertRaises(DistutilsOptionError, cmd.handle_extra_path)

    def test_finalize_options(self):
        dist = Distribution({'name': 'xx'})
        cmd = install(dist)

        # must supply either prefix/exec-prefix/home or
        # install-base/install-platbase -- not both
        cmd.prefix = 'prefix'
        cmd.install_base = 'base'
        self.assertRaises(DistutilsOptionError, cmd.finalize_options)

        # must supply either home or prefix/exec-prefix -- not both
        cmd.install_base = None
        cmd.home = 'home'
        self.assertRaises(DistutilsOptionError, cmd.finalize_options)

        # can't combine user with with prefix/exec_prefix/home or
        # install_(plat)base
        cmd.prefix = None
        cmd.user = 'user'
        self.assertRaises(DistutilsOptionError, cmd.finalize_options)

    def test_record(self):

        install_dir = self.mkdtemp()
        pkgdir, dist = self.create_dist()

        dist = Distribution()
        cmd = install(dist)
        dist.command_obj['install'] = cmd
        cmd.root = install_dir
        cmd.record = os.path.join(pkgdir, 'RECORD')
        cmd.ensure_finalized()
        cmd.run()

        # let's check the RECORD file was created with one
        # line (the egg info file)
        f = open(cmd.record)
        try:
            self.assertEquals(len(f.readlines()), 1)
        finally:
            f.close()

    def _test_debug_mode(self):
        # this covers the code called when DEBUG is set
        old_logs_len = len(self.logs)
        install_module.DEBUG = True
        try:
            __, stdout = captured_stdout(self.test_record)
        finally:
            install_module.DEBUG = False
        self.assertTrue(len(self.logs) > old_logs_len)

def test_suite():
    return unittest2.makeSuite(InstallTestCase)

if __name__ == "__main__":
    unittest2.main(defaultTest="test_suite")
