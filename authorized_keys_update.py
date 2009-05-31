#!/usr/bin/env python
"""\
Add or remove keys from an SSH authorized_keys file.

USAGE: %prog (add|remove) user key filename

This program was designed for use with git_ssh_server.py or svnserve, where
users all SSH to a particular user whose ~/.ssh/authorized_keys file has a
command="USER" option for each user's public key.
"""

from __future__ import with_statement, print_function
__metaclass__ = type

__license__ = """\
Copyright (c) 2009 Mark Lodato

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import sys, os
import re
from atomicfile import LockedAtomicFile

# The options of each authorized_keys line, with %s as the username.
OPTIONS = 'command="%s",no-port-forwarding,no-X11-forwarding,no-agent-forwarding'

class PublicKeyError (Exception): pass
class InvalidPublicKey (PublicKeyError): pass
class PublicKeyExists (PublicKeyError): pass


class PublicKey:
    """Parse a user's SSH public key (id_rsa.pub or id_dsa.pub).

    The input must be of the form "type key [comment]".  `InvalidPublicKey` is
    raised if the input is invalid.

    The type, key, and comment may be accessed as attributes.
    """

    def __init__(self, s):
        if len(s) > 8192:
            raise InvalidPublicKey('key too long (8192 bytes max)')
        groups = s.split(None, 2)
        if len(groups) < 2:
            raise InvalidPublicKey('invalid key format (must be "type key '
                    '[comment]")')
        type = groups[0]
        key = groups[1]
        try:
            comment = groups[2]
        except IndexError:
            comment = ''
        if type not in ('ssh-rsa', 'ssh-dss'):
            raise InvalidPublicKey('invalid key type (must be "ssh-rsa" or '
                    '"ssh-dsa")')
        if not re.match('^[0-9a-zA-Z+/=]{20,}$', key):
            raise InvalidPublicKey('invalid public key (must be at least 20 '
                    'base64 characters)')
        comment = comment.replace('\n', ' ')
        self.type = type
        self.key = key
        self.comment = comment

    def __str__(self):
        return ' '.join((self.type, self.key, self.comment))


def add_key(user, key, filename, options=OPTIONS):
    """Add a key to the authorized_keys file.

    user
        userid of user associated with this public key
    key
        public key supplied by the user
    filename
        path to the authorized_keys file
    options : optional
        string specifying the "options" section of the line; for example,
        'command="abc",no-pty'.  '%s' (if it exists) is substituted for
        `user`.  In order for this to work with `remove_key()`, options must
        start with 'command="%s"'.

    `PublicKeyExists` is raised if the public key already exists.
    """
    key = PublicKey(key)
    with LockedAtomicFile(filename, autobreak = True) as f:
        for line in f:
            if key.key in line:
                raise PublicKeyExists('public key already exists')
            f.write(line)
        if '%s' in options:
            options %= user
        print(options, key, file=f)
        f.commit()
    return True


def remove_key(user, key, filename):
    """Remove a key to the authorized_keys file.

    user
        userid of user associated with this public key
    key
        public key supplied by the user
    filename
        path to the authorized_keys file

    The public key is removed only if the line starts with 'command="USER"',
    where USER is `user`.

    Returns True if the key was erased, False if the key was not found.
    """
    key = PublicKey(key)
    erased = False
    start = 'command="%s"' % user
    with LockedAtomicFile(filename, autobreak = True) as f:
        for line in f:
            if line.startswith(start) and key.key in line:
                erased = True
            else:
                f.write(line)
        if erased:
            f.commit()
        else:
            f.cancel()
    return erased


def global_docstring():
    """Return the global docstring, substituting %prog for the program
    name."""
    doc = globals()['__doc__']
    return doc.replace('%prog', os.path.basename(sys.argv[0]))


def do_usage(message=None):
    """Print usage statement and exit."""
    usage = re.search(r'^USAGE:\s*(.*?)$', global_docstring(),
                      re.MULTILINE | re.IGNORECASE).group(0)
    print(usage, file=sys.stderr)
    if message:
        print('\n', message, sep='', file=sys.stderr)
    sys.exit(1)

def do_help():
    """Print help message (module docstring) and exit."""
    print(global_docstring())
    sys.exit(0)


COMMANDS = {'add' : add_key, 'remove' : remove_key}


if __name__ == "__main__":
    if '-h' in sys.argv or '--help' in sys.argv:
        do_help()
    try:
        command, user, key, filename = sys.argv[1:]
        f = COMMANDS[command]
    except (ValueError, KeyError):
        do_usage()
    if not f(user, key, filename):
        sys.exit(2)
