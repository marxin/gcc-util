#!/usr/bin/python

# List git branches which apparently refer to closed bugs in bugzilla
# (i.e. they have pr12345 in their name and pr 12345 is closed).

import sys
import re
import urllib2
from subprocess import Popen, PIPE, call
import xml.etree.ElementTree as ET

def die (s):
    "Give a string warning S to stderr and abort with exit code 1."
    sys.stderr.write (s + "\n")
    sys.exit (1)
    pass

def examine_pr_branch (branch, bugnum, verbose):
    url = ("https://gcc.gnu.org/bugzilla/show_bug.cgi?ctype=xml&id="
           + str(bugnum))
    # print url
    try:
        stream = urllib2.urlopen(url)
        tree = ET.parse(stream)
        root = tree.getroot()
        status = root.find("./bug/bug_status").text
        # resolution = root.find("./bug/resolution").text
            
        if status == "RESOLVED":
            print branch
            if verbose:
                shdesc = root.find("./bug/short_desc").text.strip()
                print (shdesc[:75])
                print ("https://gcc.gnu.org/bugzilla/show_bug.cgi?id="
                       + str(bugnum))
                bug = root.find("bug")
                lastdesc = bug.findall("long_desc")[-1]
                when = lastdesc.find("bug_when").text
                who = lastdesc.find("who")
                print ("Last comment: {0} {1}"
                       .format(when, str(who.attrib["name"])))
                print ("");
                pass
            pass
        stream.close()

    except:
        sys.stderr.write ("Failed examining branch {0}\n".format(branch))
        raise
        return
    return

def list_fixed_branches_main():

    if (len(sys.argv) >= 2
        and sys.argv[1] == "-v"):
        verbose = True
    else:
        verbose = False
        pass


    p1 = Popen (["git", "branch"], stdout=PIPE)
    o1 = p1.communicate()
    if p1.returncode != 0:
        die ("Git did not list local branches successfully");
        return
    local_branches = o1[0].split ("\n")

    for branch in local_branches:
        branch = branch.strip().lstrip("*").strip()

        match = re.search (r"pr([0-9]{4,})", branch)
        if not match:
            continue

        # print match.group(1)
        # print branch
        examine_pr_branch (branch, match.group(1), verbose)

        pass
    pass

if __name__ == '__main__':
    list_fixed_branches_main()
