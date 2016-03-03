#!/usr/bin/python

# List git branches that track a remote branch which no longer exists,
# probably because it has been deleted by "git remote prune".

import sys
from subprocess import Popen, PIPE, call

def die (s):
    "Give a string warning S to stderr and abort with exit code 1."
    sys.stderr.write (s + "\n")
    sys.exit (1)
    pass

def prune_local_branches_main():

    if (len(sys.argv) >= 2
        and sys.argv[1] == "-d"):
        dry_run = False
    else:
        dry_run = True
        pass

    p1 = Popen (["git", "branch", "-vv"], stdout=PIPE)
    o1 = p1.communicate()
    if p1.returncode != 0:
        die ("Git did not list local branches successfully");
        return
    local_branches = o1[0].split ("\n")
    
    p2 = Popen (["git", "branch", "-r"], stdout=PIPE)
    o2 = p2.communicate()
    if p2.returncode != 0:
        die ("Git did not list remote branches successfully");
        return
    remote_branches = o2[0].split ("\n")

    remotes = []
    for remline in remote_branches:
        remline = remline.strip().lstrip("*")
        if remline == "":
            continue
        br = remline.split()[0]
        remotes.append (br)

    for locline in local_branches:
        locline = locline.strip().lstrip("*")
        if locline == "":
            continue
        locname = locline.split()[0]
        remname = locline.split()[2]
        if remname[0] != "[":
            continue
        remname = remname.strip("[]")
        cidx = remname.find(":")
        if cidx >= 0:
            remname = remname[:cidx]
            pass
        
        if not remname in remotes:
            if dry_run:
                print (locname)
            else:
                print ("Deleting " + locname)
                call (["git", "branch", "-D", locname])
                pass
            pass
        pass


if __name__ == '__main__':
    prune_local_branches_main()
