#! /usr/bin/env python
#
# Configure PyInstaller for the current Python installation.
#
# Copyright (C) 2005, Giovanni Bajo
# Based on previous work under copyright (c) 2002 McMillan Enterprises, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

import os
import sys
import string
import shutil
import pprint
import re
import glob

import mf
import bindepend
import Build

HOME = os.path.dirname(sys.argv[0])

iswin = sys.platform[:3] == 'win'
is24 = hasattr(sys, "version_info") and sys.version_info[:2] >= (2,4)
cygwin = sys.platform == 'cygwin'


def find_EXE_dependencies(config):
    global target_platform, target_iswin
    print "I: computing EXE_dependencies"
    python = opts.executable or sys.executable
    target_platform = opts.target_platform or sys.platform
    config['python'] = python
    config['target_platform'] = target_platform
    target_iswin = target_platform[:3] == 'win'

    if not iswin:
        while os.path.islink(python):
            python = os.path.join(os.path.split(python)[0], os.readlink(python))

    xtrapath = []
    if target_iswin and not iswin:
        # try to find a mounted Windows system
        xtrapath = glob.glob('/mnt/*/WINDOWS/system32/')
        if not xtrapath:
            print "E: Can not find a mounted Windows system"
            print "W: Please set 'xtrpath' in the config file yourself"

    xtrapath = config.get('xtrapath') or xtrapath
    config['xtrapath'] = xtrapath

    toc = bindepend.Dependencies([('', python, '')], target_platform, xtrapath)

    if iswin and sys.version[:3] == '1.5':
        import exceptions
        toc.append((os.path.basename(exceptions.__file__), exceptions.__file__, 'BINARY'))
    config['EXE_dependencies'] = toc[1:]


_useTK = """\
# Generated by Configure.py
# This file is public domain
import os, sys
try:
    basedir = os.environ['_MEIPASS2']
except KeyError:
    basedir = sys.path[0]
tcldir = os.path.join(basedir, '_MEI', 'tcl%s')
tkdir = os.path.join(basedir, '_MEI', 'tk%s')
os.environ["TCL_LIBRARY"] = tcldir
os.environ["TK_LIBRARY"] = tkdir
os.putenv("TCL_LIBRARY", tcldir)
os.putenv("TK_LIBRARY", tkdir)
"""

def test_TCL_TK(config):
    # TCL_root, TK_root and support/useTK.py
    print "I: Finding TCL/TK..."
    if not (target_iswin):
        saveexcludes = bindepend.excludes
        bindepend.excludes = {}
    pattern = [r'libtcl(\d\.\d)?\.(so|dylib)', r'(?i)tcl(\d\d)\.dll'][target_iswin]
    a = mf.ImportTracker()
    a.analyze_r('Tkinter')
    binaries = []
    for modnm, mod in a.modules.items():
        if isinstance(mod, mf.ExtensionModule):
            binaries.append((mod.__name__, mod.__file__, 'EXTENSION'))
    binaries.extend(bindepend.Dependencies(binaries))
    binaries.extend(bindepend.Dependencies([('', sys.executable, '')]))
    for nm, fnm, typ in binaries:
        mo = re.match(pattern, nm)
        if mo:
            ver = mo.group(1)
            tclbindir = os.path.dirname(fnm)
            if target_iswin:
                ver = ver[0] + '.' + ver[1:]
            elif ver is None:
                # we found "libtcl.so.0" so we need to get the version from the lib directory
                for name in os.listdir(tclbindir):
                    mo = re.match(r'tcl(\d.\d)', name)
                    if mo:
                        ver = mo.group(1)
            print "I: found TCL/TK version %s" % ver
            open(os.path.join(HOME, 'support', 'useTK.py'), 'w').write(_useTK % (ver, ver))
            tclnm = 'tcl%s' % ver
            tknm = 'tk%s' % ver
            # Linux: /usr/lib with the .tcl files in /usr/lib/tcl8.3 and /usr/lib/tk8.3
            # Windows: Python21/DLLs with the .tcl files in Python21/tcl/tcl8.3 and Python21/tcl/tk8.3
            #      or  D:/Programs/Tcl/bin with the .tcl files in D:/Programs/Tcl/lib/tcl8.0 and D:/Programs/Tcl/lib/tk8.0
            if target_iswin:
                for attempt in ['../tcl', '../lib']:
                    if os.path.exists(os.path.join(tclbindir, attempt, tclnm)):
                        config['TCL_root'] = os.path.join(tclbindir, attempt, tclnm)
                        config['TK_root'] = os.path.join(tclbindir, attempt, tknm)
                        break
            else:
                config['TCL_root'] = os.path.join(tclbindir, tclnm)
                config['TK_root'] = os.path.join(tclbindir, tknm)
            break
    else:
        print "I: could not find TCL/TK"
    if not target_iswin:
        bindepend.excludes = saveexcludes

def test_Crypt(config):
    # TODO: disabled for now
    config["useCrypt"] = 0
    return 

    #Crypt support. We need to build the AES module and we'll use distutils
    # for that. FIXME: the day we'll use distutils for everything this will be
    # a solved problem.
    print "I: trying to build crypt support..."
    from distutils.core import run_setup
    cwd = os.getcwd()
    try:
        os.chdir(os.path.join(HOME, "source", "crypto"))
        dist = run_setup("setup.py", ["install"])
        if dist.have_run.get("install", 0):
            config["useCrypt"] = 1
            print "I: ... crypto support available"
        else:
            config["useCrypt"] = 0
            print "I: ... error building crypto support"
    finally:
        os.chdir(cwd)

def test_Zlib(config):
    #useZLIB
    print "I: testing for Zlib..."
    try:
        import zlib
        config['useZLIB'] = 1
        print 'I: ... Zlib available'
    except ImportError:
        config['useZLIB'] = 0
        print 'I: ... Zlib unavailable'

def test_RsrcUpdate(config):
    config['hasRsrcUpdate'] = 0
    if not iswin:
        return
    # only available on windows
    print "I: Testing for ability to set icons, version resources..."
    try:
        import win32api, icon, versionInfo
    except ImportError, detail:
        print 'I: ... resource update unavailable -', detail
        return
    
    test_exe = os.path.join(HOME, 'support', 'loader', 'run_7rw.exe')
    if not os.path.exists( test_exe ):
        config['hasRsrcUpdate'] = 0
        print 'E: ... resource update unavailable - %s not found' % test_exe
        return

    # The test_exe may be read-only
    # make a writable copy and test using that
    rw_test_exe = os.path.join( os.environ['TEMP'], 'me_test_exe.tmp' )
    shutil.copyfile( test_exe, rw_test_exe )
    try:
        hexe = win32api.BeginUpdateResource(rw_test_exe, 0)
    except:
        print 'I: ... resource update unavailable - win32api.BeginUpdateResource failed'
    else:
        win32api.EndUpdateResource(hexe, 1)
        config['hasRsrcUpdate'] = 1
        print 'I: ... resource update available'
    os.remove(rw_test_exe)


_useUnicode = """\
# Generated by Configure.py
# This file is public domain
import %s
"""

_useUnicodeFN = os.path.join(HOME, 'support', 'useUnicode.py')

def test_unicode(config):
    print 'I: Testing for Unicode support...'
    try:
        import codecs
        config['hasUnicode'] = 1
        try:
            import encodings
        except ImportError:
            module = "codecs"
        else:
            module = "encodings"
        open(_useUnicodeFN, 'w').write(_useUnicode % module)
        print 'I: ... Unicode available'
    except ImportError:
        try:
            os.remove(_useUnicodeFN)
        except OSError:
            pass
        config['hasUnicode'] = 0
        print 'I: ... Unicode NOT available'

def test_UPX(config):
    print 'I: testing for UPX...'
    hasUPX = 0
    try:
        vers = os.popen("upx -V").readlines()
        if vers:
            v = string.split(vers[0])[1]
            hasUPX = tuple(map(int, string.split(v, ".")))
            if iswin and is24 and hasUPX < (1,92):
                print 'E: UPX is too old! Python 2.4 under Windows requires UPX 1.92+'
                hasUPX = 0
        print 'I: ...UPX %s' % (('unavailable','available')[hasUPX != 0])
    except Exception, e:
        print 'I: ...exception result in testing for UPX'
        print e, e.args
    config['hasUPX'] = hasUPX


def find_PYZ_dependencies(config):
    print "I: computing PYZ dependencies..."
    a = mf.ImportTracker([os.path.join(HOME, 'support')])
    a.analyze_r('archive')
    mod = a.modules['archive']
    toc = Build.TOC([(mod.__name__, mod.__file__, 'PYMODULE')])
    for i in range(len(toc)):
        nm, fnm, typ = toc[i]
        mod = a.modules[nm]
        tmp = []
        for importednm, isdelayed, isconditional, level in mod.imports:
            if not isconditional:
                realnms = a.analyze_one(importednm, nm)
                for realnm in realnms:
                    imported = a.modules[realnm]
                    if not isinstance(imported, mf.BuiltinModule):
                        tmp.append((imported.__name__, imported.__file__, imported.typ))
        toc.extend(tmp)
    toc.reverse()
    config['PYZ_dependencies'] = toc.data


def main(configfilename):
    try:
        config = Build._load_data(configfilename)
        print 'I: read old config from', configfilename
    except IOError, SyntaxError:
        # IOerror: file not present/readable
        # SyntaxError: invalid file (platform change?)
        # if not set by Make.py we can assume Windows
        config = {'useELFEXE': 1}

    # Save Python version, to detect and avoid conflicts
    config["pythonVersion"] = sys.version
    config["pythonDebug"] = __debug__

    find_EXE_dependencies(config)
    test_TCL_TK(config)
    test_Zlib(config)
    test_Crypt(config)
    test_RsrcUpdate(config)
    test_unicode(config)
    test_UPX(config)
    find_PYZ_dependencies(config)

    Build._save_data(configfilename, config)
    print "I: done generating", configfilename


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options]")
    parser.add_option('--target-platform', default=None,
                      help='Target platform, required for cross-bundling '
                           '(default: current platform).')
    parser.add_option('--executable', default=None,
                      help='Python executable to use. Required for '
                           'cross-bundling.')
    parser.add_option('-C', '--configfile',
                      default=os.path.join(HOME, 'config.dat'),
                      help='Name of generated configfile (default: %default)')

    opts, args = parser.parse_args()
    if args:
        parser.error('Does not expect any arguments')

    main(opts.configfile)
