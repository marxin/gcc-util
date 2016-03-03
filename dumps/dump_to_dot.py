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
hadgoto = True;
no_statements = 0
empty_bbs = set()

gcclabel_re = re.compile ("(^<bb [0-9]+>)|(^L\.[0-9]+)|(^<L[0-9]+>)")
goto_re = re.compile ("goto <bb [0-9]+>")
switch_re = re.compile ("switch \([^)<]+\) <.*>$")

def process_line (line):
    """Process a line in the assembly input"""
    global curbb, bbs, availbbs, edges, condbbs, hadgoto;
    global gcclabel_re, goto_re, nobb, no_statements, empty_bbs;

    hi = line.find ('#')
    if (hi <> -1):
        line = line[0:hi]
        pass

    line = line.strip ()
    if len(line) == 0:
        return

    ci = line.find (':')
    if (ci <> -1):
        label = line[:ci]
        if (gcclabel_re.match (label)):
            if (not hadgoto):
                edges.append ((curbb, label, 0))
#                print "IMPLICIT GOTO  to %s" % label
                if no_statements == 0:
                    empty_bbs.add (curbb)
                    pass
                pass
            elif no_statements == 1:
                empty_bbs.add (curbb)
                pass
            
            curbb = label
            hadgoto = False
            no_statements = -1
#            print "NEW BB %s" % curbb

            if (curbb in availbbs):
                sys.stderr.write ("WARNING: bb %s encountered more than once\n"
                                  % curbb);
            else:
                availbbs.add (curbb);
                bbs.append (curbb);
                pass
            return
        pass

    no_statements = no_statements + 1

    if (goto_re.match (line)):
        target = line[5:].rstrip(";")

        pi = target.find("(");
        if (pi <> -1):
#            sys.stderr.write ("WEIRD TARGET %s\n" % target)
            target = target[pi+1:-1]
            pass
        
        if hadgoto:
            truelabel = 0
        else:
            truelabel = 1
        if (hadgoto):
            condbbs.add (curbb)
#            print "   BB %s marked as ending with a condition" % curbb
            pass
        edges.append ((curbb, target, truelabel));
#        print "GOTO %s, truelabel: %s" % (target, truelabel)
        hadgoto = True
        return

    if (switch_re.match (line)):
#        sys.stderr.write ("PROCESSING SWITCH %s\n" % line)
        pi = line.find ("<")
        cls = line[pi+1:-1]
        cl = cls.split(",")
        for c in cl:
            l = c[c.find(":")+1:].strip()
            edges.append ((curbb, l, 2));
            continue
        condbbs.add (curbb)
        hadgoto = True
        return
    
    if line.find ("return") == 0:
        hadgoto = True;
        return
    return

def print_bbs ():
    """Print all the basic block as dot nodes"""
    global bbs, empty_bbs;

    for bb in bbs:
        if bb in empty_bbs:
            attrs = '[style=filled, fillcolor=yellow, label="%s"];' % bb
            pass
        else:
            attrs = '[label="%s"];' % bb
            pass
        print ('\t"%s"' % bb) + attrs


def print_edges ():
    """Print all the edges in dot fashion"""
    global curbb, bbs, edges, condbbs;

    for src, dst, tl in edges:
        if (src in condbbs):
            if tl == 0:
                label = "false"
            elif tl == 1:
                label = "true"
            elif tl == 2:
                label = "switch"
            else:
                label = "unknown type"
            print '\t"%s" -> "%s" [taillabel="%s"];' % (src, dst, label)
        else:
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
