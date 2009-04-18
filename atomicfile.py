"""
A portable, safe impementation of lock files and atomic writes.

See the `Lock`, `AtomicFile`, and `LockedAtomicFile` for details.
"""

__author__ = "Mark Lodato <lodatom-at-gmail>"

__license__ = """
This is the MIT license: http://www.opensource.org/licenses/mit-license.php

Copyright (c) 2009 Mark Lodato

The Lock class is based on `lockfile.py`, which is
    Copyright (c) 2007 Skip Montanaro
and located at:
    http://bitbucket.org/bignose/python-lockfile/src/tip/lockfile.py

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.
"""


import os as _os
import shutil as _shutil


class LockTimeoutError (RuntimeError):
    """Called when Lock times out."""


class Lock (object):
    """
    A mkdir-based lock file.

    When `acquire()` is called, attempts to make a directory named by the
    `path` argument.  This operation is portable - it works on Windows and
    Unices, and it works over NFS.  If a lock already exists, it retries every
    `wait` seconds until `timeout` seconds have elapsed.  On timeout, if
    `autobreak` is true, breaks the existing lock and retries; otherwise
    raises `LockTimeoutError`.

    The preferred method is to use a with statement:
    >>> with Lock('foo.lock'):
    ...     open('foo').read()

    A manual `acquire()` and `release()` is also allowed.
    >>> lock = Lock('bar.lock', autobreak=True)
    >>> f.acquire()
    >>> os.system('touch bar')
    >>> f.release()
    """

    # Defaults:
    TIMEOUT = 5.0
    WAIT = 0.1
    AUTOBREAK = False
    NONCE_SIZE = 8
    PREFIX = 'lock'
    JOINER = '_'

    def __init__(self, path, timeout=None, wait=None, autobreak=None):

        from random import Random
        from string import letters
        from socket import gethostname

        # Use class-wide default if an argument is None.
        if wait is None:            wait = self.WAIT
        if timeout is None:         timeout = self.TIMEOUT
        if autobreak is None:       autobreak = self.AUTOBREAK

        # Set instance's default options.
        self.wait = wait
        self.timeout = timeout
        self.autobreak = autobreak

        self.path = path
        nonce = ''.join( Random().choice(letters)
                         for x in range(self.NONCE_SIZE) )
        self.unique_basename = self.JOINER.join([
                self.PREFIX,
                gethostname(),
                str(_os.getpid()),
                nonce,
                ])
        self.unique = _os.path.join(self.path, self.unique_basename)

    def __del__(self):
        self.release()

    def acquire(self, timeout=None, wait=None, autobreak=None):
        """
        Acquire the lock.

        See the class documentation for details on this function.  If the
        optional arguments are not given, the instance's defaults are used.
        """

        from errno import EEXIST
        from sys import exc_info
        import time

        # Use instance's default if argument is None.
        if wait is None:        wait = self.wait
        if timeout is None:     timeout = self.timeout
        if autobreak is None:   autobreak = self.autobreak

        end_time = time.time() + timeout

        while True:
            try:
                _os.mkdir(self.path)
            except OSError:
                err = exc_info()[1]
                if err.errno == EEXIST:
                    # Already locked
                    if self.acquired():
                        # Already locked by me.
                        return
                    if time.time() > end_time:
                        if autobreak:
                            # Break the lock and try again.
                            self.break_lock()
                            end_time = time.time() + timeout
                        else:
                            raise LockTimeoutError
                    time.sleep(wait)
                else:
                    raise
            else:
                # Lock succeeded
                open(self.unique, 'wb').close()
                return

    def release(self):
        """
        Relase the lock.

        If it was not acquired, does nothing.
        """
        if not self.acquired():
            return
        _os.unlink(self.unique)
        _os.rmdir(self.path)

    def break_lock(self, force=False):
        """
        Break an existing lock.

        If `force`, unconditionally remove the entire lock directory tree.
        Otherwise, only break the lock if all files within the lock directory
        start with `self.PREFIX`.
        """
        if force:
            _shutil.rmtree(self.path)
        else:
            if _os.path.exists(self.path):
                for name in _os.listdir(self.path):
                    if not name.startswith(self.PREFIX):
                        raise UnlockError('non-lock file in lock directory: '
                                + name)
                    _os.unlink(_os.path.join(self.path, name))
                _os.rmdir(self.path)

    def acquired(self):
        """Return True if the lock exists and was acquired by this instance,
        False otherwise."""
        return _os.path.exists(self.unique)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_exc):
        self.release()


class AtomicFile (object):
    """
    A file update whose writes are atomic and safe from server crashes.

    When a new instance is created, the destination file (`filename`) is
    opened in read-only mode as the attribute `input`.  It is also
    copied to `tmp_filename` (default: `filename`+".tmp") and that file is
    opened in write-only mode as the attribute `output`.

    When finished writing, call `commit()` to save the changes to disk, or
    `cancel()` to throw away the temporary file.  If neither has been called
    when `close()` is called without arguments, as is done at the exit of
    a with-statement, the changes are committed only if `autocommit` is true.
    If neither has been done when the instance is deleted, `cancel()` is
    called.

    >>> with AtomicFile("foo.txt") as f:
    ...     for line in f:
    ...         line.replace('foo', 'bar')
    ...         f.write(line)
    ...     f.commit()
    """

    # Defaults
    TMP_EXT = ".tmp"
    AUTOCOMMIT = False
    BINARY = False

    def __init__(self, filename, tmp_filename=None, autocommit=None,
            binary=None):

        if tmp_filename is None:
            tmp_filename = filename + self.TMP_EXT
        if autocommit is None:
            autocommit = self.AUTOCOMMIT
        if binary is None:
            binary = self.BINARY

        # Attributes
        self.filename = filename
        self.tmp_filename = tmp_filename
        self.autocommit = autocommit
        self.closed = False

        if binary:
            binary = "b"
        else:
            binary = ""

        # Open the original file as input and the temporary file as output.
        _shutil.copy2(self.filename, self.tmp_filename)
        self.input = open(self.filename, "r" + binary)
        self.output = open(self.tmp_filename, "w" + binary)

        # Some convenience methods to read from the input file.
        self.read = self.input.read
        self.readline = self.input.readline
        self.readlines = self.input.readlines
        self.next = self.input.next

        # Some convenience methods to write to the input file.
        self.write = self.output.write
        self.writelines = self.output.writelines

    def __del__(self):
        """Calls `cancel()`."""
        self.cancel()

    def __enter__(self):
        """Simply returns `self`."""
        return self

    def __iter__(self):
        return iter(self.input)

    def __exit__(self, type, exc_value, traceback):
        """Calls `close()` if no exceptions; otherwise `cancel()`."""
        if type is None and exc_value is None and traceback is None:
            self.close()
        else:
            self.cancel()
        return False

    def close(self, commit=None):
        """
        Close the files and commit if `commit`, cancel otherwise.

        Both `input` and `output` are closed.  If `commit`, flushes the
        buffers, synchronizes the write, and atomically copies the temporary
        file to the destination.  If not `commit`, deletes the temporary file.

        If `commit` is None, it is set to `self.autocommit`.

        If the file is already closed, does nothing.
        """
        if self.closed:
            return
        if commit is None:
            commit = self.autocommit
        self.input.close()
        if commit:
            self.output.flush()
            _os.fsync(self.output.fileno())
        self.output.close()
        if commit:
            _os.rename(self.tmp_filename, self.filename)
        else:
            _os.remove(self.tmp_filename)
        self.closed = True

    def cancel(self):
        """Cancel the update - same as `close(False)`."""
        self.close(False)

    def commit(self):
        """Commit the update - same as `close(True)`."""
        self.close(True)


class LockedAtomicFile (AtomicFile):
    """
    A safe, atomic, (advisory) locked file implementation.

    This class operates as `AtomicFile`, except a `Lock` is acquired before
    opening and is released after closing.

    >>> with LockedAtomicFile("foo.txt") as f:
    ...     for line in f:
    ...         line.replace('foo', 'bar')
    ...         f.write(line)
    ...     f.commit()
    """

    LOCK_EXT = ".lock"

    def __init__(self, filename, tmp_filename=None, binary=None,
            autocommit=None, lock_filename=None, timeout=None,
            wait=None, autobreak=None):

        if lock_filename is None:
            lock_filename = filename + self.LOCK_EXT

        self.lock = Lock(lock_filename, timeout=timeout, wait=wait,
                autobreak=autobreak)
        self.lock.acquire()

        try:
            super(LockedAtomicFile,self).__init__(filename,
                    tmp_filename=tmp_filename, binary=binary,
                    autocommit=autocommit)
        except:
            self.lock.release()
            raise


    def close(self, commit=None):
        if self.closed:
            return
        super(LockedAtomicFile,self).close(commit=commit)
        self.lock.release()
