.. role:: file (emphasis)

==============
git-ssh-server
==============

Description
===========


This software is designed to be an (almost) entirely ssh-based public git
hosting server; think GitHub_ or Gitorious_ without the web server.  This
offers three main advantages: the administrator doesn't need to set up a web
server, the end user can do everything through the command line, and I (the
author) don't have to do any web programming (at which I suck).  The only part
you must do out-of-band (e.g. through a web server) is signing up users; I
will add this feature soon.

.. _GitHub: http://www.github.com
.. _Gitorious: http://www.gitorious.org


Repository Types
================

Repositories are broken into three types, which specify the permissions of the
repository: *user*, *group*, and *public*.


User Repositories
-----------------

User repositories are owned by a particular user and are of the following
form::

    u/owner.git

That is, user repositories begin with "u/", followed by the username of the
owner of the repository, and end with ".git".  The "u" denotes that it is a
*user* repository (as opposed to *group* and *public*, below), and all
repository paths end in ".git".

Additionally, user repositories may be nested arbitrarily within
subdirectories.  Examples::

    u/owner/repo.git
    u/owner/dir/repo.git
    u/owner/dir/subdir/repo.git

... and so on.  Anyone may read a user repository, but only the owner may
write to one.  Also, only the owner may create, delete, or rename repositories
within the owner's directory.

There is one exception: any repositories located within a subdirectory named
"private" are readable only by the owner.  For example, "u/mark/pub.git" will
be readable by all, but "u/mark/private/secret.git" will be readable only by
"mark".


Group Repositories
------------------

Group repositories act just like user repositories, except the "owner" is a
group of users, rather than a single user, and the prefix is "g/" instead of
"u/".  Examples::

    g/group.git
    g/group/repo.git

and so on.  Just like user repositories, anyone may read from group
repositories (except those in a "private" subdirectory).  Any member of the
group may write to, create, delete, and rename repositories within the group's
directory.

Unfortunately, group management is not yet implemented in the user interface.
This will hopefully come soon.


Public Repositories
-------------------

Public repositories follow the same naming scheme as user and group
repositories, but begin with "p/".  Examples::

    p/project.git
    p/project/devel.git
    p/project/subproject/foo.git

Unlike user and group repositories, public repositories are not owned by
anyone and, therefore, are readable and writable by all.  In the public name
space, "private" directories are not allowed.

Though there are no owners of public repositories, the second component of the
path ("project" in the above examples) is suggested to be a project name.  In
that way, related repositories can be grouped together.  We suggest having the
"official" (or stable) repository be "p/project.git", while any development
repositories or related side projects be within the "p/project/" directory
structure.



Package Layout
==============

This package contains the following scripts:

:file:`git_ssh_server.py`
    The main "server" that interacts with users.  The manual page is below.

:file:`generate_cgitrc.py`
    Scans the repository directory and generates a configuration file
    suitable for inclusion by cgit_.  Currently it is designed to be run as a
    cron job; in the future, I may incorporate this functionality directly
    into :file:`git_ssh_server.py`.

:file:`authorized_keys_update.py`
    A script/module for atomically updating the ~/.git/authorized_keys file.

In addition, there exist the following support files:

:file:`atomicfile.py`
    A module that performs file locking and/or atomic writes.

:file:`odict.py`
    An implementation of an ordered dictionary.

:file:`COPYING`
    A copy of the AGPL3.

:file:`README.rst`
    This file.

.. _cgit: http://hjemli.net/git/cgit/


Manual Page for git_ssh_server.py
=================================

NAME
----

``git_ssh_server.py`` - A more useful git-shell.

SYNOPSIS
--------

``git_ssh_server.py user``

``git_ssh_server.py (--help | --man)``

DESCRIPTION
-----------

Run commands from ``$SSH_ORIGINAL_COMMAND`` as a git restricted shell,
allowing access only to the directories accessible by given user.

This script is usually run automatically by ssh.  Suppose the user *jsmith*
runs the following::

    ssh git@server create foo

On *server*, :file:`~git/.ssh/authorized_keys` is configured to run the
following::

    SSH_ORIGINAL_COMMAND='create foo' git_ssh_server.py jsmith

This is the same basic model as git-shell(1), except that many more commands
are available to the user, and permissions are checked for various operations.


AVAILABLE COMMANDS
------------------

To use this server, run one of the following commands on the ``ssh`` command
line.  For example: ``ssh git@hostname list mine``.

**help** [*command*]
    If *command* is given, print out the help for that command. Otherwise,
    list the available commands.

**list**
    List all available repositories.

**create** *path*
    Create a new repository located at *path*.  The path must end in ".git",
    must not be contained in another repository, and must not already exist.

**fork** *existing-path* *new-path*
    Fork (make a copy of) an existing repository.  The same rules for
    **create** apply to *new-path*.

**rename** *existing-path* *new-path*
    Change the path an existing repository.  The same rules for **create**
    apply to *new-path*.  **WARNING**: Once you perform this operation, users
    who have set up a remote to this repository will have to change their
    configuration to point to the new path.

In addition, the following commands are called indirectly by the end user's
``git`` program.

**git-upload-pack** *path*
    Called by ``git fetch`` and ``git clone``.

**git-receive-pack** *path*
    Called by ``git push``.


CONFIGURATION
-------------

The following directions were modified from
http://eagain.net/blog/2007/03/22/howto-host-git.html.

1. Create a *git* user. ::

    sudo adduser \
        --system \
        --home /var/www/git \
        --no-create-home \
        --shell /bin/sh \
        --gecos 'git version control' \
        --group \
        --disabled-password \
        git

2. For each user, add an authorized_keys entry to
   :file:`~git/.ssh/authorized_keys`.  Replace "jdoe" with the user's id, and
   "..." with the user's public SSH key.  Each entry must be on a single
   line.  ::

    command="/path/to/git_ssh_server.py jdoe",no-port-forwarding,no-X11-forwarding,no-agent-forwarding ssh-rsa ... jdoe@example.com


BUGS
----

``$SSH_ORIGINAL_COMMAND`` strips quotes and mashes all the arguments together,
so if any argument has a space in it, it is parsed as a separate argument.
Unless you allow paths with spaces in them, this is not a problem.

There is no checking of lock files, so if you delete or rename a repository
while someone is fetching, bad stuff may happen.


TODO
----

Add group management stuff.

Add options to the **list** command.

Call ``git update-server-info`` after a push?

Add a way of setting the project description for cgit/gitweb.

Ideas for future commands:

* show - display project info
* cat - cat file of HEAD
* ls - directory list of HEAD
* find - like find(1) command?
* follow - like github's follow?
* config - set project meta-data?


AUTHOR
------

Mark Lodato <lodatom-at-gmail>


LICENSE
-------

`GNU Affero General Public License, Version 3`_

Contact the author if you wish to obtain a different license.


.. _GNU Affero General Public License, Version 3:
    http://www.fsf.org/licensing/licenses/agpl-3.0.html
