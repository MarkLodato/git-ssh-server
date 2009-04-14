
import fcntl
import os


class AtomicLockedFile (object):
    """
    A safe, atomic, (advistory) locked file implementation.

    >>> with AtomicLockedFile("foo.txt") as f:
    ...     for line in f:
    ...         line.replace('foo', 'bar')
    ...         f.write(line)
    ...     f.commit()
    """
    """
    Details:

    0) get the file contents (read it or make it somehow)
    1) open temp file
    2) write contents to temp file
    3) fsync()
    4) close temp file
    5) rename temp file to original file
    """

    DEFAULT_TMP_EXT = ".tmp"
    DEFAULT_LOCK_EXT = ".tmp.lock"
    DEFAULT_AUTOCOMMIT = False

    def __init__(self, filename, tmp_ext=None, lock_ext=None,
            autocommit=None):

        if tmp_ext is None:
            tmp_ext = self.DEFAULT_TMP_EXT
        if lock_ext is None:
            lock_ext = self.DEFAULT_LOCK_EXT
        if autocommit is None:
            autocommit = self.DEFAULT_AUTOCOMMIT

        # Attributes
        self.filename = filename
        self.tmp_filename = filename + tmp_ext
        self.lock_filename = filename + lock_ext
        self.autocommit = autocommit
        self.closed = False

        # File object attributes
        self.lock = open(self.lock_filename, "w")
        fcntl.lockf(self.lock, self.LOCK_EX)
        self.tmp = open(self.tmp_filename, "w")
        self.f = open(filename, "r")

        # Methods to read from the input file
        self.read = self.f.read
        self.readline = self.f.readline
        self.readlines = self.f.readlines
        self.__iter__ = self.f.__iter__
        self.next = self.f.next

        # Methods to write to the temporary file
        self.write = self.tmp.write
        self.writelines = self.tmp.writelines

    def __del__(self):
        self.cancel()

    def __enter__(self):
        return self

    def __exit__(self, type, exc_value, traceback):
        if type is None and exc_value is None and traceback is None:
            self.close()
        else:
            self.cancel()
        return False

    def close(self, commit=None):
        if self.closed:
            return
        if commit is None:
            commit = self.autocommit
        self.f.close()
        if commit:
            self.tmp.flush()
            os.fsync(self.tmp.fileno())
        self.tmp.close()
        if commit:
            os.rename(self.tmp_filename, self.filename)
        else:
            os.remove(self.tmp_filename)
        os.remove(self.lock_filename)
        self.lock.close()
        self.closed = True

    def cancel(self):
        self.close(False)

    def commit(self):
        self.close(True)
