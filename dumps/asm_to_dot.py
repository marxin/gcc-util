#!/usr/bin/python
import sys
import re
import fileinput

def die (s):
    "Give a string warning S to stderr and abort with exit code 1."
    sys.stderr.write (s + "\n")
    sys.exit (1)


nobb = "ENTER"
curbb = nobb
bbs = [];
availbbs = set ()
edges = [];
condbbs = set ()
callbbs = set ()
mmbbs = set ()
uncondjump = True;
call_edges = [];

gcclabelre = re.compile ("L[0-9]+");

def process_line (line):
    """Process a line in the assembly input"""
    global curbb, bbs, availbbs, mmbbs, edges, condbbs, callbbs, uncondjump;
    global gcclabelre, nobb, call_edges;

    line = line.strip ()

    hi = line.find ('#')
    if (hi <> -1):
        line = line[0:hi]

    ci = line.find (':')
    if (ci <> -1):
        label = line[:ci].lstrip(".")
        if (label.find("B") == 0) or (gcclabelre.match (label)):
            if (not uncondjump):
                edges.append ((curbb, label, False))

            curbb = label
            if (curbb in availbbs):
                sys.stderr.write ("WARNING: bb %s encountered more than once\n"
                                  % curbb);
            else:
                availbbs.add (curbb);
                bbs.append (curbb);

            uncondjump = False;
        line = line[ci+1:]

    ji = line.find ("j")
    if (ji == 0):
        if (len (line) > 3) and (line[1] == "m") and (line[2] == "p"):
            target = line[3:].strip ().strip (".")
#            print "UNCONDITIONAL jump to %s" % target
            uncondjump = True
            truelabel = False
        else:
            if uncondjump:
                if curbb == nobb:
                    # gcc does not start with a BB label
                    bbs.append (curbb);
                    uncondjump = False;
                else:
                    sys.stderr.write ("WARNING: Cond jump after uncond " +
                                      ("jump in %s\n" % curbb));

            if line[2].isspace():
                target = line[2:].strip ().strip (".")
            else:
                target = line[3:].strip ().strip (".")

            condbbs.add (curbb)
            truelabel = True;
#            print "COND jump to %s" % target
        edges.append ((curbb, target, truelabel));

    if line.find ("call") == 0:
        callbbs.add (curbb);
        call_count = len (call_edges)+1;
        target = "%s__call_no_%i" % (line[4:].strip (), call_count)
        call_edges.append ((curbb, target))
    if line.find ("ret") == 0:
        uncondjump = True;
    if (line.find ("%xmm") >= 0) or (line.find ("%ymm") > 0):
        mmbbs.add(curbb);


def print_bbs ():
    """Print all the basic block as dot nodes"""
    global bbs, callbbs, mmbbs;


    for bb in bbs:
        if bb in callbbs:
            attrs =  '[style=filled, fillcolor=green, label="%s"];' % bb
        else:
            if bb in mmbbs:
                attrs = ('[style=filled, fillcolor=magenta, ' +
                         'label="%s"];') % bb
            else:
                attrs = '[label="%s"];' % bb
        print ('\t"%s"' % bb) + attrs

#            print '\tnode [style=filled, fillcolor=green, label="%s"];' % bb
#        else:
#            print '\tnode [label="%s"];' % bb
#        print '\t"%s";' % bb


def print_edges ():
    """Print all the edges in dot fashion"""
    global curbb, bbs, edges, condbbs, call_edges;

    for src, dst, tl in edges:
        if (src in condbbs):
            if tl:
                label = "true"
            else:
                label = "false"

            print '\t"%s" -> "%s" [taillabel="%s"];' % (src, dst, label)
        else:
            print '\t"%s" -> "%s";' % (src, dst);

    for src, dst in call_edges:
        print '\t"%s" -> "%s";' % (src, dst);


def print_output ():
    """Print the dot graph"""

    print """digraph G {
	node [shape=box, fontsize=10, height=0.2];
	edge [color=gray30,fontsize=10];\n"""

    print_bbs ()

    #so that all bbs we missed can be identified:
    print "\n\tnode [shape=ellipse];\n"

    print_edges ()

    print "}"




def main():
    """The main function."""

    global N

    if (len (sys.argv) < 2):
        die ("""You need to specify the input file.  CFG in dot format will be
then printed to stdout""")

    for line in fileinput.input():
        process_line (line)

    print_output ();


if __name__ == '__main__':
    main()
