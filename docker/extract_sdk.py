#!/usr/bin/env python2.7
"""Extract the NAOqi SDK without relying on external tar/coreutils binaries."""
import glob
import os
import tarfile
import sys


def main(archive_path, destination):
    if not os.path.isdir(destination):
        os.makedirs(destination)

    archive = tarfile.open(archive_path, "r:gz")
    try:
        members = []
        for member in archive.getmembers():
            parts = member.name.split("/", 1)
            if len(parts) != 2 or not parts[1]:
                continue
            relative_name = parts[1]
            if relative_name.startswith("/") or ".." in relative_name.split("/"):
                raise ValueError("Unsafe SDK archive path: %s" % member.name)
            member.name = relative_name
            members.append(member)
        archive.extractall(destination, members=members)
    finally:
        archive.close()

    # Use the interpreter and standard library from the base image consistently.
    for path in glob.glob(os.path.join(destination, "lib", "libpython2.7.so*")):
        os.unlink(path)
    os.remove(archive_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: extract_sdk.py ARCHIVE DESTINATION")
    main(sys.argv[1], sys.argv[2])
