#!/usr/bin/env python

import os, os.path, sys


def owner_of(url):
    c = url.split('/')
    prefix = c[0]
    if prefix == 'p':
        owner = 'everyone!'
    else:
        owner = c[1]
    if owner.endswith('.git'):
        owner = owner[:-3]
    if prefix == 'g':
        owner = 'g/' + owner
    return owner

def generate_cgitrc(base_path, outfile):
    base_path = os.path.join(base_path, '')     # append a slash
    base_len = len(base_path)
    for root, dirs, files in os.walk(base_path):
        if root.endswith('.git'):
            dirs[:] = []        # descend no further
            url = root[base_len:]
            outfile.write('\nrepo.url=%s\n' % url)
            outfile.write('repo.owner=%s\n' % owner_of(url))
            if 'description' in files:
                filename = os.path.join(root, 'description')
                try:
                    f = open(filename)
                    desc = f.readline().strip()
                    f.close()
                except IOError:
                    pass
                else:
                    outfile.write('repo.desc=%s\n' % desc)


def main(base_path, outfilename):
    if outfilename == '-':
        generate_cgitrc(base_path, sys.stdout)
    else:
        tmpfilename = outfilename + '.tmp'
        f = open(tmpfilename, 'w')
        try:
            generate_cgitrc(base_path, f)
        except:
            f.close()
            os.remove(tmpfilename)
            raise
        else:
            f.flush()
            os.fsync(f.fileno())
            f.close()
            os.rename(tmpfilename, outfilename)


if __name__ == "__main__":
    try:
        base_path, outfilename = sys.argv[1:]
    except ValueError:
        print >>sys.stderr, __module__.__doc__
        sys.exit(1)
    main(base_path, outfilename)

