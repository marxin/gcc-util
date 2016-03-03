#!/usr/bin/python

import glob
import fileinput
import os
import sys
import subprocess
import re
#import copy from copy
import pickle



def die (s):
    "Give a string warning S to stderr and abort with exit code 1."
    sys.stderr.write(s + "\n")
    sys.exit(1)
    pass

# list of includes which are not necessary, indexed by the file containing them
unnecessary_includes = {}

# indexed by dependent, contains set of required providers on which it depends
depending_on = {}
# indexed by provider, contains set of files depending on the provider
providing_for = {}
# indexed by tuple (provider, dependent), contains a list of actual
# error messages which are generated if the dependence is not met
reasons = {}

# indexed by typle (provider, dependent), contains the list of files
# which we compiled in order to get that error
when_compiling = {}

def add_dep (changed_file, err_file, include, message):
    global depending_on, providing_for, reasons, when_compiling

#    print ("   add_dep({}, {}, ...)".format (err_file, include))


    if "/" in err_file:
        err_file = err_file[err_file.rindex("/")+1:]

    if err_file in depending_on:
        depending_on[err_file].add(include)
    else:
        depending_on[err_file] = set([include])
        
    if include in providing_for:
        providing_for[include].add(err_file)
    else:
        providing_for[include] = set([err_file])

    mkey = (include, err_file)
    if mkey in reasons:
        if not message in reasons[mkey]:
            reasons[mkey].append(message)
    else:
        reasons[mkey] = [message]

    if mkey in when_compiling:
        if not changed_file in when_compiling[mkey]:
            when_compiling[mkey].append(changed_file)
    else:
        when_compiling[mkey] = [changed_file]

    return
    
def parse_errors (changed_file, include, errors):

    err_re = re.compile("([^:]+):(\d+):\d+: error: (.*)")
    i = 0
    j = 0
    while True:
        while i < len(errors):
            if ("error:" in errors[i]):
                break
            if ("warning:" in errors[i]):
                j = i + 1
            i = i + 1
            continue
        
        if i >= len(errors):
            return

        mo = err_re.match(errors[i])
        if not mo:
            # Ld errors and such
            print (("ERROR: Somehow the error regular expression did not match "
                    + "on line {}").format(errors[i]))
            i = i + 1
            j = i
            continue

        err_file = mo.group(1)
        err_message = mo.group(3)
        
        interesting_include = ""
        while (j < i):
            if errors[j].startswith("In file included from "):
                interesting_include = ""
                assert ":" in errors[j]
                prev_include = errors[j][22:errors[j].index(':')]
                j = j + 1
                while ((j < i)
                       and errors[j].startswith("                 from ")):
                    interesting_include = prev_include
                    assert ":" in errors[j]
                    prev_include = errors[j][22:errors[j].index(':')]
                    j = j + 1
                    continue
                pass
            else:
                # errors happening during macro expansion have the above
                # explaining where the expansion happens, not where the problem
                # is
                interesting_include = ""
                j = j + 1
                pass
            continue
                    
        if interesting_include != "":
            err_file = interesting_include
            pass

        if not err_file.endswith(changed_file):
            add_dep (changed_file, err_file, include, err_message) 
        i = i + 1
        j = i
        continue



def try_compiling (changed_file, include):
    global unnecessary_includes

    os.chdir("../../obj");
    cmd = subprocess.Popen("make > /dev/null", shell=True,
                           stderr=subprocess.PIPE)
    errors = []
    for line in cmd.stderr:
        if not line.startswith("make"):
            errors.append (line.rstrip("\n"))
        pass
        
    if cmd.wait() == 0:
        print ("Compilation succeeded")
        ret = False
        if changed_file in unnecessary_includes:
            unnecessary_includes[changed_file].append(include)
        else:
            unnecessary_includes[changed_file] = [include]
            pass
    else:
        parse_errors (changed_file, include, errors)
        ret = True
    return ret
        


def process_file (filename):
    i = 1
    includes = []

    if os.system ("git reset --hard &> /dev/null") != 0:
        die("git reset --hard failed")
        return
    for line in fileinput.input(filename):
        if (line.startswith ('#include "') and line.rstrip().endswith('.h"')
            and (not line.startswith ('#include "config.h"'))
            and (not line.startswith ('#include "tm.h"'))
            and (not line.startswith ('#include "system.h"'))
            and (not line.startswith ('#include "gt-'))
            and (not line.startswith ('#include "coretypes.h"'))):
            includes.append (i)
            pass
        i = i + 1
        pass

    srcpath = os.getcwd()
    for omit in includes:
        if os.system ("git reset --hard &> /dev/null") != 0:
            die("git reset --hard failed")
            return
        i = 1
        include = ""
        for line in fileinput.input(filename, inplace=True):
            if i == omit:
                print("")
                include = line[line.index('"') + 1:]
                include = include[:include.index('"')]
            else:
                print(line.rstrip("\n"))
                pass
            i = i + 1
            pass

        print ("Compiling {}, omitting include {} at line {}".format (filename,
                                                                      include,
                                                                      omit))
        try_compiling (filename, include)
        os.chdir (srcpath)
        pass


def ascii_error (message):
    udata = message.decode("utf-8")
    return udata.encode("ascii","ignore")

def output_report (depending_on, providing_for, reasons, unnecessary_includes,
                   when_compiling):
    print("Generating textual reports")
    f = open('dependencies-full.txt', 'w')
    t = open('dependencies-terse.txt', 'w')
    for dependant in sorted(depending_on.keys(),
                            key=lambda x: len(depending_on[x]),
                            reverse=True):
        t.write("\n{} requires the following files:\n".format(dependant))
        f.write("\n{} requires the following files:\n".format(dependant))
        for prov in depending_on[dependant]:
            t.write("  - {}\n".format(prov))
            f.write("  - {} in order to supress the following errors:\n".format(
                prov))
            for r in reasons[(prov, dependant)]:
                f.write("      + {}\n".format(ascii_error(r)))
            f.write("    when compiling files:\n")
            f.write("      {}\n".format(", ".
                                        join(when_compiling[(prov, dependant)])))
    f.close()
    t.close()

    f = open('provides-full.txt', 'w')
    t = open('provides-terse.txt', 'w')
    for prov in sorted(providing_for.keys(),
                       key=lambda x: len(providing_for[x]),
                       reverse=True):
        t.write ("\n{} provides stuff for the following files:\n".format(prov))
        f.write ("\n{} provides stuff for the following files:\n".format(prov))
        for dep in providing_for[prov]:
            t.write("  - {}\n".format(dep))
            f.write("  - {} so that it avoids the following errors:\n".format(
                dep))
            for r in reasons[(prov, dep)]:
                f.write("      + {}\n".format(ascii_error(r)))
            f.write("    when compiling files:\n")
            f.write("      {}\n".format(", ". join(when_compiling[(prov, dep)])))
    f.close()
    t.close()

    f = open('unnecessary.txt', 'w')
    f.write ("\n---- Superfluous includes: ----\n")
    for unn in sorted(unnecessary_includes.keys()):
        f.write("\nFile {} unnecessarily includes the following files:\n".format(
            unn))
        f.write("  {}".format(", ".join(unnecessary_includes[unn])))


    f.close()
    return

def edge_interesting_for_graph (d, p, specnode):
    if d == specnode:
        return True
    if p in ["is-a.h", "vec.h"]:
        return False
    if d in ["system.h", "libiberty.h", "ggc.h", "vec.h"]:
        return False
    if p.startswith("gt-") or d.startswith("gt-"):
        return False
    if p.endswith(".def") or d.endswith(".def"):
        return False
    return True

def output_dot (nodes, deps, output_file_name, specnode):
    print("Generating dot file {}".format(output_file_name))
    f = open(output_file_name, "w")
    
    f.write("digraph G {\n")
    f.write("\tedge [color=gray30,fontsize=10];\n")

    if specnode:
        f.write('\t"{}"[style=filled, fillcolor=blue, fontcolor=white];\n'.
                format(specnode))

    if nodes:
        nodes = set ()
        for d in deps.keys():
            for p in deps[d]:
                if edge_interesting_for_graph (d, p, specnode):
                    nodes.add (d)
                    nodes.add (p)
        for n in sorted(nodes):
            f.write('\t"{}";\n'.format(n))

    for d in deps.keys():
        for p in deps[d]:
            if edge_interesting_for_graph (d, p, specnode):
                f.write('\t"{}" -> "{}";\n'.format(d, p))
    f.write("}\n")

    f.close()
    return

def derive_frequencies (depending_on, providing_for):
    print ("Freqencies of dependencies:")

    depfreq = {}
    for deps in depending_on:
        k = len(deps)
        if k in depfreq:
            depfreq[k] = depfreq[k] + 1
        else:
            depfreq[k] = 1;

    bars = []
    for k in range(1, max(depfreq.keys())+1):
        if k in depfreq:
            v = depfreq[k]
        else:
            v = 0
        bars.append(v)
        print ("{}, {}".format(k, v))


    print ("Freqencies of provides:")

    provfreq = {}
    for prov in providing_for:
        k = len(prov)
        if k in provfreq:
            provfreq[k] = provfreq[k] + 1
        else:
            provfreq[k] = 1;
    for k in range(1, max(provfreq.keys())+1):
        if k in provfreq:
            v = provfreq[k]
        else:
            v = 1
        print ("{}, {}".format(k, v))

    return


def process_results (depending_on, providing_for, reasons, unnecessary_includes,
                     when_compiling):

    output_report(depending_on, providing_for, reasons, unnecessary_includes,
                  when_compiling)
    output_dot(set(depending_on.keys()) | set(providing_for.keys()),
               depending_on, "dependencies_graph.dot", None)
    derive_frequencies (depending_on, providing_for)

    for spec in ["tree.h", "basic-block.h", "vec.h", "rtl.h", "function.h",
                 "cfgloop.h", "cgraph.h", "input.h", "gimple.h", "df.h"]:
        spec_dep = {}
        spec_dep[spec] = depending_on[spec]
        for p in depending_on[spec]:
            if p in depending_on:
                spec_dep[p] = depending_on[p]
            
        output_dot (None, spec_dep,
                    "deps-of-{}.dot".format(spec.replace(".","-")),
                    spec)
    

    return            

def main():
    global depending_on, providing_for, reasons, unnecessary_includes
    global when_compiling

    pickle_file_name = 'pickled_dependencies.pkl'

    if os.path.isfile(pickle_file_name):
        print ("Unpickling results");

        pkl_file = open(pickle_file_name, 'rb')
        depending_on = pickle.load(pkl_file)
        providing_for = pickle.load(pkl_file)
        reasons = pickle.load(pkl_file)
        unnecessary_includes = pickle.load(pkl_file)
        when_compiling = pickle.load(pkl_file)
        pkl_file.close()
    else:
        files_to_process = glob.glob("*.c")
        i = 1
        for filename in files_to_process:
            print ("Processing file {} out of {}".format(i,
                                                         len (files_to_process)))
            process_file (filename)
            i = i + 1
            pass

        print ("Pickling results");
        output = open(pickle_file_name, 'wb')
        pickle.dump(depending_on, output, -1)
        pickle.dump(providing_for, output, -1)
        pickle.dump(reasons, output, -1)
        pickle.dump(unnecessary_includes, output, -1)
        pickle.dump(when_compiling, output, -1)
        output.close()

    process_results (depending_on, providing_for, reasons, unnecessary_includes,
                     when_compiling)
    return

if __name__ == '__main__':
    main()

