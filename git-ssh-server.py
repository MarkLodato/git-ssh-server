#!/usr/bin/env python

# Copyright 2009 Mark Lodato
#
#    This program is free software: you can redistribute it and/or modify it
#    under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or (at
#    your option) any later version.
#
#    This program is distributed in the hope that it will be useful, but
#    WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero
#    General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program (see COPYING).  If not, see
#    <http://www.gnu.org/licenses/>.
#
# If you would like to use this software under a different license, please
# contact Mark Lodato at <lodatom-at-gmail>.

# Make Python 2 act like Python 3.
from __future__ import with_statement, division
__metaclass__ = type        # default to new-style classes

import sys, os
import textwrap
import shlex
import re
import os.path
import contextlib
import subprocess
try:
    from odict import OrderedDict
except ImportError:
    OrderedDict = dict

class Error (Exception): pass
class ArgumentError (Error): pass
class UsageError (Error): pass
class InvalidPath (Error): pass
class PermissionError (Error): pass


config = {
        'project_dir' : '.config',
        'base_path' : './repos',
        'git'       : '/usr/local/bin/git',
        }


class Backend:

    def __init__(self, user, config):
        self.user = user
        self.base_path = config['base_path']
        self.project_dir = config['project_dir']
        self.git_cmd = config['git']


    # Internal commands:

    valid_prefix = '[upg]'
    valid_name = '[a-zA-Z0-9_-]+'
    valid_path_RE = re.compile(r'^(%(prefix)s)/(%(name)s)(/%(name)s)*\.git$'
            % {'name' : valid_name, 'prefix' : valid_prefix})
    MAX_PATH_LEN = 255


    def transform_path(self, path, existing=True, write=True):
        """Transform a path from the user to a path on disk.

        Raises InvalidPath if the path is not valid, or if `existing` is True
        and the path does not exist.

        Raises PermissionError if the user does not have permission to perform
        a write (if `write`, else read).

        Returns (`realpath`, `prefix`, `base`), with `realpath` being the path
        on disk, `prefix` being one of 'u' (user), 'g' (group), or 'p'
        (project), and `base` being the leading path component (corresponding
        to a user, group, or project.)
        """
        path = path.strip('/')
        if len(path) > self.MAX_PATH_LEN:
            raise InvalidPath("Path is too long")
        m = self.valid_path_RE.match(path)
        if m is None:
            raise InvalidPath("Invalid path specification")
        realpath = os.path.join(self.base_path, path)
        if existing and not os.path.exists(realpath):
            raise InvalidPath("Repository '%s' does not exist" % path)
        if not existing and os.path.exists(realpath):
            raise InvalidPath("Repository '%s' already exists" % path)
        prefix = m.group(1)
        base = m.group(2)
        if write:
            operation = 'write'
        else:
            operation = 'read'
        self.validate(realpath, operation, prefix, base)
        if prefix == 'p' and '/private/' in path:
            raise InvalidPath("Private directories not allowed in projects")
        return realpath

    def validate(self, realpath, operation, prefix, base):
        """Validate that the user has permission to access the given path.

        `operation` must be 'read' or 'write'.

        Raises PermissionError if the user does not have permission to perform
        `operation`.  Otherwise returns None.
        """
        # If the path has "/private/" in it, or if write access is requested,
        # only allow owner(s) access.
        if (operation != 'read') or ('/private/' in realpath):
            if not self.is_member(prefix, base):
                if operation == 'read':
                    raise PermissionError('repository is private')
                else:
                    raise PermissionError('permission denied')

    def is_member(self, prefix, base):
        """Return True if the curent user is a member of the given base."""
        if prefix == 'u':
            return base == self.user
        elif prefix == 'p':
            return True
        elif prefix == 'g':
            membersfile = os.path.join(self.base_path, prefix, base,
                    self.project_dir, 'members')
            with open(membersfile, 'r') as f:
                for line in f:
                    if line.strip() == token:
                        return True
            return False
        else:
            raise ValueError("undefined prefix: `%s'" % prefix)

    def run(self, *command, **kwargs):
        return subprocess.call(command, **kwargs)

    def git(self, *args, **kwargs):
        args = list(args)
        for k,v in kwargs.iteritems():
            k = k.replace('_','-')      # git uses -'s, python uses _'s
            if v is True:
                v = "--%s" % k
            else:
                v = "--%s=%s" % (k,v)
            if k in ("git-dir",):
                args.insert(0, v)
            else:
                args.append(v)
        return self.run(self.git_cmd, *args)


    # External commands:

    def git_upload_pack(self, path):
        path = self.transform_path(path, write=False)
        return self.git("upload-pack", path)


    def git_receive_pack(self, path):
        path = self.transform_path(path)
        return self.git("receive-pack", path)


    def create(self, path):
        path = self.transform_path(path, existing=False)
        os.makedirs(path)
        # TODO --template
        return self.git("init", bare=True, quiet=True, git_dir=path)


    def fork(self, old, new):
        old = self.transform_path(old, write=False)
        new = self.transform_path(new, existing=False)
        os.makedirs(new)
        # TODO --template
        return self.git("clone", old, new, bare=True, quiet=True, mirror=True)


    def rename(self, old, new):
        old = self.transform_path(old)
        new = self.transform_path(new, existing=False)
        os.rename(old, new)


    def list(self, *args):
        # For now, just try listing all the .git directories
        # TODO don't show /private/ repos?
        # TODO add options for limiting?
        out = []
        for root, dirs, files in os.walk(self.base_path):
            if root.endswith('.git'):
                dirs[:] = []
                out.append(root.lstrip(self.base_path))
        return out



class Frontend:

    def __init__(self, backend):
        self.backend = backend


    @staticmethod
    def _confirm(prompt=None, default=False):
        """Present a confirmation to the user on standard output."""

        answers = {
                'y' : True,
                'yes' : True,
                'n' : False,
                'no' : False,
                }

        if prompt is None:
            prompt = 'Confirm'

        if default:
            prompt += ' [Y/n] '
        else:
            prompt += ' [y/N] '

        while True:
            ans = raw_input(prompt).lower()
            if not ans:
                return default
            try:
                return answers[ans]
            except KeyError:
                print 'please enter y or n.'


    def _format_help(self, f):
        """Strip off common leading whitespace from a docstring."""
        doc = f.__doc__
        if doc is None:
            return None
        lines = doc.split('\n')
        first = lines.pop(0)
        rest = '\n'.join(lines)
        formatted = '\n'.join((first, textwrap.dedent(rest)))
        return formatted.strip()


    def _get_desc(self, f):
        """Return the description of a function (first non-blank line of
        docstring."""
        doc = f.__doc__
        if doc is None:
            return "(undocumented)"
        lines = [x  for x in doc.split('\n')  if x.strip()]
        try:
            return lines[0].strip()
        except IndexError:
            return "(undocumented)"


    def _get_usage(self, f):
        """Return the usage statement of a function (second non-blank line of
        docstring."""
        doc = f.__doc__
        if doc is None:
            return "(undocumented)"
        lines = [x  for x in doc.split('\n')  if x.strip()]
        try:
            return lines[1].strip()
        except IndexError:
            return "(undocumented)"



    def help(self, args):
        """
        Describe usage of the program and its commands.

        USAGE: help [command]

        If `command` is given, print out the help for that command. Otherwise,
        list the available commands.
        """
        if len(args) <= 1:
            print "Available commands:"
            for name, f in self.commands.iteritems():
                desc = self._get_desc(f)
                print "    %-19s %s" % (name, desc)
            print "\nRun 'help <cmd>' for help on a specific command."
        else:
            cmd = args[1]
            try:
                f = self.commands[cmd]
            except KeyError:
                self.unknown_command([cmd])
            else:
                doc = self._format_help(f)
                if doc is None:
                    doc = "Command '%s' is undocumented" % cmd
                print doc


    def git_upload_pack(self, args):
        """
        Called by 'git-fetch-pack'.

        USAGE: git-upload-pack <directory>

        See the man page for git-upload-pack.
        """
        if len(args) != 2:
            raise UsageError()
        self.backend.git_upload_pack(args[1])


    def git_receive_pack(self, args):
        """
        Called by 'git-send-pack'.

        USAGE: git-receive-pack <directory>

        See the man page for git-receive-pack.
        """
        if len(args) != 2:
            raise UsageError()
        return self.backend.git_receive_pack(args[1])


    def list(self, args):
        """
        List available repositories.

        USAGE: list <TODO>

        TODO
        """
        # TODO parse the arguments
        repos = self.backend.list(*args)
        if len(repos) == 0:
            print "No repositories found."
        else:
            for r in repos:
                print r


    def create(self, args):
        """
        Create a new repository.

        USAGE: create <path>

        The path to the repository must end in ".git", must not be contained
        within another repository. and must not exist.  That is, it must match
        one of the following regular expressions:

            u/USER(/[a-zA-Z0-9_-]+)*\.git

        Examples:
            u/USER.git
            u/USER/foo.git
            u/USER/bar/baz.git
        """
        if len(args) != 2:
            raise UsageError()
        rc = self.backend.create(args[1])
        if rc == 0:
            print "Successfully created '%s'" % (args[1])
        return rc


    def rename(self, args):
        """
        Rename (move) an existing repository.

        USAGE: rename <old_path> <new_path>

        Rename (move) an existing repository to a new name.  The new
        name must be valid; see "help create" for more information.

        *Warning* This operation is potentially unsafe. All clones of this
        repository must update the remote to the new path or else fetching
        and pulling will no longer work.
        """
        if len(args) != 3:
            raise UsageError()

        # is this necessary?
        print "Renaming a repository will break all clones."
        if not self._confirm("Are you sure you wish to proceed?"):
            print "Operation cancelled"
            return 0

        rc = self.backend.rename(args[1], args[2])
        if rc == 0:
            print "Successfully renamed '%s' to '%s'" % (args[1], args[2])


    def fork(self, args):
        """
        Fork (make a copy of) an existing repository.

        USAGE: fork <existing_path> <new_path>

        Make a copy of an existing repository.  The new name must be valid;
        see "help create" for more information.
        """
        if len(args) != 3:
            raise UsageError()
        rc = self.backend.fork(args[1], args[2])
        if rc == 0:
            print "Successfully forked '%s' to '%s'" % (args[1], args[2])
        return rc


    def unknown_command(self, args):
        """Called when a command is not found."""
        raise Error("Unknown command: '%s'; run 'help' for a list of commands."
                % args[0])


    commands = OrderedDict([
            ("help"             , help),
            ("list"             , list),
            ("create"           , create),
            ("rename"           , rename),
            ("fork"             , fork),
            ("git-upload-pack"  , git_upload_pack),
            ("git-receive-pack" , git_receive_pack),

            # Not implemented yet:
            #("delete"           , delete),
            #("undelete"         , undelete),

            # Ideas:
            #("config",          , config), # set project meta-data
            #("show",            , show),   # project info
            #("cat",             , cat),    # cat file
            #("ls",              , ls),     # directory list
            #("find",            , find),   # like find command?
            #("follow",          , follow), # like github's follow
            ])


    def interpret(self, cmdline):
        """Interpret the given command line."""
        try:
            args = shlex.split(cmdline)
        except ValueError, e:
            print >>sys.stderr, "Error parsing command line:", e
        cmd = args[0]
        f = self.commands.get(cmd, type(self).unknown_command)
        rc = 1
        try:
            rc = f(self, args)
        except UsageError, e:
            usage = self._get_usage(f)
            msg = str(e)
            if msg:
                print >>sys.stderr, "ERROR:", msg, "\n"
            print >>sys.stderr, usage
        except Error, e:
            print >>sys.stderr, "ERROR:", e
        except NotImplementedError, e:
            print >>sys.stderr, "Command '%s' is not yet implemented" % cmd
        else:
            if rc is None:
                rc = 0
        return rc



def main(argv, cmd):
    if len(argv) != 2 or not cmd:
        raise ArgumentError("USAGE: SSH_ORIGINAL_COMMAND='cmd' %s user"
                % argv[0])

    user = argv[1]
    b = Backend(user, config)
    f = Frontend(b)
    f.interpret(cmd)


if __name__ == "__main__":
    try:
        rc = main(sys.argv, os.environ.get('SSH_ORIGINAL_COMMAND'))
    except Error, e:
        print >>sys.stderr, e
        sys.exit(1)
    else:
        if rc is None:
            rc = 0
        sys.exit(rc)
