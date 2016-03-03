#!/usr/bin/python

import sys
import re

def die (s):
    "Give a string warning S to stderr and abort with exit code 1."
    sys.stderr.write (s + "\n")
    sys.exit (1)
    return

def pre_process_line (line):
    line = line.strip ()
    line = re.sub (r"/[^/]*/(obj|b-obj)/", "/path/", line)
    line = re.sub (r"\.c\.[0-9]{3}([itr])\.", r".c.\1.", line)
    line = re.sub (r"/(gcc|mjambor)/[^/]*/src/libffi/", r"/gccsource/path/src/libffi/", line)
    line = re.sub (r"/[^/]*/[^/]*/libsanitizer/", "/libsanitizerpath/", line)
    if "asan" in line:
        i = line.find("==")
        if i >= 0:
            line = line[:i + 2]
            pass
        pass

    return line;

def index_from_prefix (line):
    if line.startswith ("PASS:"):
        return 0
    elif line.startswith ("FAIL:"):
        return 1
    elif line.startswith ("XPASS:"):
        return 2
    elif line.startswith ("XFAIL:"):
        return 3
    elif line.startswith ("ERROR:"):
        return 4
    elif line.startswith ("UNSUPPORTED:"):
        return 5
    elif line.startswith ("UNRESOLVED:"):
        return 5
    return -1
    

def value_from_line (line):
    i = line.find(":")
    assert (i >= 0), "Getting a value from a line without a colon"
    v = line[i+1:]
    return v

def add_line_to_dict (line, d):
    v = value_from_line (line)
    if v in d:
        d[v] = d[v] + 1
    else:
        d[v] = 1
    return

def remove_ref_from_dict (v, d):
    c = d[v] - 1
    if c == 0:
        del d[v]
    else:
        d[v] = c;
        pass
    return

def main():
    """The main function."""

    if (len (sys.argv) < 3):
        die ("Specfy the two sum files to compare")
        pass

    names = ["PASSED", "FAILED", "XPASSED", "XFAILED", "ERRED",
             "WERE UNSUPPORTED", "WERE UNRESOLVED"]
    ref = [ {} for x in xrange (len(names))]

    try:
        f1 = open (sys.argv[1], 'r')
    except:
        print ("ERROR - COULD NOT OPEN {0}".format (sys.argv[1]))
        sys.exit (1)
        return

    try:
        for line in f1:
            line = pre_process_line (line)
            i = index_from_prefix (line)
            if i >= 0:
                add_line_to_dict (line, ref[i])
                pass
            continue
    finally:
        f1.close ()
        pass

    changes = [[ [] for x in xrange (len(names))] for x in xrange (len(names))]
    new = [ [] for x in xrange (len(names))]

    try:
        f2 = open (sys.argv[2], 'r')
    except:
        print ("ERROR - COULD NOT OPEN {0}".format (sys.argv[2]))
        sys.exit (1)
        return
        
    try:
        for line in f2:
            line = pre_process_line (line)

            n = index_from_prefix (line)
            if n < 0:
                continue
        
            v = value_from_line (line)
            found = False

            if v in ref[n]:
                found = True
                remove_ref_from_dict (v, ref[n])
            else:
                for i in xrange (len(names)):
                    if i != n and v in ref[i]:
                        found = True
                        remove_ref_from_dict (v, ref[i])
                        changes[i][n].append (v)
                        pass
                    continue

            if not found:
                new[n].append (v);
                continue

            continue

    finally:
        f2.close ()
        pass

    for i in xrange (1, 5):
        if len(new[i]) > 0:
            print ("NEW tests that {0}\n".format (names[i]))
            for s in new[i]:
                print (s)
                continue
            print ("")
            pass
        continue
   
    for i in xrange (len(names)):
        for j in xrange (len(names)):
            if i != j and len(changes[i][j]) > 0:
                s = "Tests that previously {0} but now {1}:\n"
                print (s.format (names[i], names[j]))
                for s in changes[i][j]:
                    print(s)
                    continue
                print ("")
                pass
            continue
        continue
                    
    if len (new[0]) > 0:
        print ("NEW tests that PASSED:\n")
        for s in new[0]:
            print (s)
            continue
        print ("")
        pass

    for i in xrange (len(names)):
        if len(ref[i].keys()) > 0:
            s = "Tests that previously {0} that DISAPPEARED:\n"
            print (s.format (names[i]))
            for s in ref[i].keys():
                print (s)
                continue
            print ("")
            pass
        continue

if __name__ == '__main__':
    main()
