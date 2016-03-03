#!/usr/bin/python

# Script counting nuber of calles, and their callees etc of a
# function.  Started as a verification of a hypothesis but it shows
# use of the python symtab thingy well too.

import sys
import re
from symtab import *

def die (s):
    "Give a string warning S to stderr and abort with exit code 1."
    sys.stderr.write (s + "\n")
    sys.exit (1)
    pass


processed = set()
count = 0
next_report = 1000000;
max_depth = 0;
callee_sum = long(0)
stack_vec = []
max_stack = []

def process_function (f, d):
    global processed, count, next_report, max_depth;
    global callee_sum, stack_vec, max_stack

    stack_vec.append (f)
    processed.add (f.order);

    count = count + 1;
    if count > next_report:
        next_report = next_report + 1000000;
        print ("Current count is {:d}".format (count))
        pass

    if max_depth < d:
        print ("New max depth is {:d}, count is {:d}".format (d, count))
        max_depth = d;
        max_stack = stack_vec[:]
        pass

    callee_sum = callee_sum + len(f.callees)
    for callee in f.callees:
        if not callee.order in processed:
            process_function (callee, d + 1);
            pass

    processed.remove (f.order);
    stack_vec.pop ()
    return

def main():
    """The main function."""
    global max_depth, count, callee_sum, max_stack

    if (len (sys.argv) < 3):
        die ("""You need to specify the symtab name and the top func sym order.""")
        pass

    tab = DumpSymtab()
    tab.load_from_dump (sys.argv[1])

    try:
        top_order = int(sys.argv[2]);
    except:
        die ("""The second parameter is not a number""");
        pass
    
    top_symbol = tab.order_to_sym[top_order];
    print ("Top symbol is {:s}".format (top_symbol))
    
    process_function (top_symbol, 1);
    print ("Max depth was {:d}, count is {:d}".format (max_depth, count))
    print ("Callee sum: {:d}".format (callee_sum))
    print ("Number of functions: {:d}".format (len(tab.all_functions)))
    print ("Max stack:")
    for i in max_stack:
        print ("   {:s}".format (i))
        pass

if __name__ == '__main__':
    main()
