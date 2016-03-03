# A series of python scripts to convert symtab in a runnig program (or
# core dump) into the python.py representation and commands to
# visualise it.  Mostly intended for my talk at Suse Labs conference
# but it should still be useful because it is able to visualize a
# callgraph from within gdb.

import gdb
import sys
import tempfile
sys.path.append("/home/mjambor/gcc/analyze")
sys.path.append("/home/jamborm/gcc/analyze")
import symtab
from symtab import Symbol, Function, Variable, Symtab
from gdbbasic import *

symtab = None

def get_symbol_name_order(gdbval):
    """Return tuple with name and symbol order of symbol table node gdbval"""
    return (symtab_node_name (gdbval), int(gdbval["order"]))


def bool_attr_list(gdbval, candidates):
    """Return pruned candidates containing only flags that are set in gdbval"""

    r = []
    for i in candidates:
        if long (gdbval[i]) != 0:
            r.append(i)
            pass
        pass
    return r

def bool_attr_list_1(gdbval, candidates):
    """Like above but now candidates are tuples of real flag and user visible name"""

    r = []
    for i in candidates:
        if long (gdbval[i[0]]) != 0:
            r.append(i[1])
            pass
        pass
    return r

def load_symtab_base_attrs(self):
    """To be made method.  Loads common attributes from symbol base"""
    sym = self.gdbval
    vis = bool_attr_list (sym, ["in_other_partition",
                                "used_from_other_partition", "force_output",
                                "forced_by_abi", "externally_visible"])

    vis.extend(bool_attr_list_1(sym["decl"]["base"],
                                [("asm_written_flag", "asm_written"),
                                 ("public_flag", "public")]))
    vis.extend(bool_attr_list_1(sym["decl"]["decl_common"],
                                [("decl_flag_1", "external"),
                                 ("virtual_flag", "virtual"),
                                 ("artificial_flag", "artificial")]))
    vis.extend(bool_attr_list_1(sym["decl"]["decl_with_vis"],
                                [("common_flag", "common"),
                                 ("weak_flag", "weak"),
                                 ("dllimport_flag", "dll_import"),
                                 ("comdat_flag", "comdat"),
#                                 ("x_comdat_group", "one_only"),
                                 ("visibility_specified",
                                  "visibility_specified")]))
#    cg = sym["decl"]["decl_with_vis"]["comdat_group"]
#    if (long(cg) != 0):
#        vis.append("comdat_group:%s" % tree_get_identifier_str (cg))
#        pass
#    sn = sym["decl"]["decl_with_vis"]["section_name"]
#    if (long(sn) != 0):
#        vis.append("section_name:%s" & sn["string"]["str"].string())
#        pass
    visnum = long(sym["decl"]["decl_with_vis"]["visibility"])
    if visnum != 0:
        visnames = gdb.parse_and_eval("visibility_types")
        vistype_str = visnames[visnum].string()
        vis.append("visibility:%s" % vistype_str)
        pass
    resnum = int(sym["resolution"])
    if resnum != 0:
        resnames = gdb.parse_and_eval("ld_plugin_symbol_resolution_names")
        res_str = resnames[resnum].string()
        vis.append(res_str)
        pass

    self.visibility = vis

    if sym["address_taken"]:
        self.address_taken = True
        pass
    
    return

def gather_references_orders (gdbval):
    """Return orders of nodes ipa_ref_list references"""
# TODO: Somehow also note speculative references and attributes in
# general
    vec = gdbval["references"]
    return [int(i["referred"]["order"]) for i in vec_iter(vec)]

def gather_referring_orders (gdbval):
    """Return orders of nodes referring node associated with ipa_ref_list"""
# TODO: Somehow also note speculative references and attributes in
# general
    vec = gdbval["referring"]
    return [int(i["referring"]["order"]) for i in vec_iter(vec)]

avail_strings = ["unset", "not_available", "overwritable", "available",
                 "local"]

class GdbFunction (Function):
    """Call graph node loaded from the real thing through gdb"""

    def __init__(self, table, gdbval):
        (name, order) = get_symbol_name_order (gdbval)
        Function.__init__ (self, table, name, order)

        cgraph_node_type = gdb.lookup_type("cgraph_node").pointer()
        self.gdbval = gdbval.cast(cgraph_node_type)
        self.load_symtab_base_attrs = load_symtab_base_attrs
        self.load_symtab_base_attrs(self)

        sym = self.gdbval
        self.visibility.extend(
            bool_attr_list_1(sym["decl"]["function_decl"],
                             [("static_ctor_flag", "constructor"),
                              ("static_dtor_flag", "destructor")]))
        
        try:
            avnum = long(gdb.parse_and_eval(
                    "cgraph_function_body_availability ((cgraph_node *) 0x%x)"
                    % long(self.gdbval)))
            self.availability = avail_strings[avnum]
        except:
            self.availability = "N/A"
            pass
        
        self.attrs = bool_attr_list(self.gdbval,
                                    ["process", "only_called_at_startup",
                                     "only_called_at_exit", "tm_clone"])
        self.attrs.extend(
            bool_attr_list(self.gdbval["local"],
                           ["local", "redefined_extern_inline"]))
        # TODO: body, executed and nested flags are missing

        self.references_orders = gather_references_orders (sym["ref_list"])
        self.referring_orders = gather_referring_orders (sym["ref_list"])

        e = self.gdbval["callers"]
        while long(e) != 0:
            self.callers_orders.append(int(e["caller"]["order"]))
            e = e["next_caller"]
            pass

        e = self.gdbval["callees"]
        while long(e) != 0:
            self.callees_orders.append(int(e["callee"]["order"]))
            e = e["next_callee"]
            pass

        inlined_to = self.gdbval["global"]["inlined_to"]
        if long(inlined_to) != 0:
            self.is_inlined = True
            self.inlined_to_order = int(inlined_to["order"])
            pass

        clone_of = self.gdbval["clone_of"]
        if long(clone_of) != 0:
            self.is_clone = True
            self.clone_of_order = int(clone_of["order"])
            pass
            
        if long(self.gdbval["thunk"]["thunk_p"]) != 0:
            self.is_thunk = True
            pass
        return


class GdbVariable (Variable):
    """Call varpool node loaded from the real thing through gdb"""

    def __init__(self, table, gdbval):
        (name, order) = get_symbol_name_order (gdbval)
        Variable.__init__ (self, table, name, order)

        cgraph_node_type = gdb.lookup_type("varpool_node").pointer()
        self.gdbval = gdbval.cast(cgraph_node_type)
        sym = self.gdbval
        self.load_symtab_base_attrs = load_symtab_base_attrs
        self.load_symtab_base_attrs(self)

        try:
            if bool(gdb.parse_and_eval("cgraph_function_flags_ready")):
                avnum = long(gdb.parse_and_eval(
                        ("cgraph_variable_initializer_availability "
                         + "((cgraph_node *) %s)") % self.gdbval))
                self.availability = avail_strings[avnum]
            else:
                self.availability = "not-ready"
        except:
            self.availability = "N/A"
            pass
        
        if long(self.gdbval["output"]) != 0:
            self.attrs = ["output"]
        else:
            self.attrs = []
            pass
        if long(sym["decl"]["decl_common"]["initial"]) != 0:
            self.attrs.append("initialized")
        if long(sym["decl"]["base"]["readonly_flag"]) != 0:
            self.attrs.append("read-only")
        # TODO Missing const-value-known attribute

        self.references_orders = gather_references_orders (sym["ref_list"])
        self.referring_orders = gather_referring_orders (sym["ref_list"])

        return

def build_gdb_symbol_table():
    """Build and return our representation of the symbol table"""

    tab = Symtab()
    n = gdb.parse_and_eval ("symtab->nodes")
    while (long(n)):
        if symtab_node_is_function (n):
            current_symbol = GdbFunction(tab, n)
            tab.all_functions.append (current_symbol)
        elif symtab_node_is_variable (n):
            current_symbol = GdbVariable(tab, n)
            tab.all_variables.append (current_symbol)
        else:
            raise gdb.GdbError ("Encountered an unknown symbol table node");

        tab.order_to_sym[current_symbol.order] = current_symbol
        tab.all_symbols.append (current_symbol)

        n = n["next"]
        pass

    tab.fixup()
    return tab


#symbol_table = None

#class BuildSymTabRepr (gdb.Command):
#    """Gdb command to build the symbol table and store it to symbol_table"""
#
#    def __init__(self):
#        gdb.Command.__init__(self, "symtab_build", gdb.COMMAND_USER)
#        return
#
#    def invoke (self, arg_str, from_tty):
#        global symbol_table
#        argv = gdb.string_to_argv(arg_str)
#        if len (argv) != 0:
#            raise gdb.GdbError ("No arguments to build the symtab");
#      
#        tab = build_gdb_symbol_table()
#        symbol_table = tab
#        return


class ListSymTabRepr (gdb.Command):
    """Gdb command to list the symbol table to gdb pager"""

    def __init__(self):
        gdb.Command.__init__(self, "symtab_list", gdb.COMMAND_USER)
        return

    def flags(self, f):
        """Return text describing important edge flags or empty string"""
        if f.is_inlined:
            return " (inlined)"
        return ""

    def invoke (self, arg_str, from_tty):
        argv = gdb.string_to_argv(arg_str)
        if len (argv) != 0:
            raise gdb.GdbError ("No arguments to list the symtab");
      
        tab = build_gdb_symbol_table()

        for f in tab.all_functions:
            gdb.write("%s/%i 0x%x\n" % (f.name, f.order, long(f.gdbval)))
            if f.is_clone:
                gdb.write("  Clone of %s\n" % str(f.clone_of))
                pass
            if f.is_inlined:
                gdb.write("  Inlined into %s\n" % str(f.inlined_to))
                pass
            gdb.write("  Visibility: " + " ".join(f.visibility))
            gdb.write("\n")
            gdb.write("  Availability: %s\n" % f.availability)
            gdb.write("  Callers: " + ", ".join(["%s/%i%s" % (i.name, i.order,
                                                              self.flags(f))
                                                 for i in f.callers]))
            gdb.write("\n")
            gdb.write("  Callees: " + ", ".join(["%s/%i%s" % (i.name, i.order,
                                                              self.flags(i))
                                                 for i in f.callees]))
            gdb.write("\n")
            gdb.write("  References: " + ", ".join(["%s/%i" % (i.name, i.order)
                                                    for i in f.references]))
            gdb.write("\n")
            gdb.write("  Referring: " + ", ".join(["%s/%i" % (i.name, i.order)
                                                   for i in f.referring]))
            gdb.write("\n\n")
            pass
        for v in tab.all_variables:
            gdb.write("%s/%i 0x%x" % (v.name, v.order, long(v.gdbval)))
            gdb.write("\n")
            gdb.write("  References: " + " ".join(["%s/%i" % (i.name, i.order)
                                                   for i in v.references]))
            gdb.write("\n")
            gdb.write("  Referring: " + " ".join(["%s/%i" % (i.name, i.order)
                                              for i in v.referring]))
            gdb.write("\n\n")
            pass
        return
            
class VisualiseSymTabRepr (gdb.Command):
    """Gdb command to visualize the symbol table with dot and feh"""

    def __init__(self):
        gdb.Command.__init__(self, "symtab_visualize", gdb.COMMAND_USER)
        self.filenum = 1
        self.dirname = tempfile.mkdtemp(prefix="gdbpython-")
        return

    def invoke (self, arg_str, from_tty):
        from symtab import display_dot

        argv = gdb.string_to_argv(arg_str)
        if "clones" in argv:
            clones = True
            pass
        else:
            clones = False
            pass

        if "nonames" in argv:
            only_orders = True
            pass
        else:
            only_orders = False
            pass
      
        if "onlyreftof" in argv:
            only_ref_to_f = True
            pass
        else:
            only_ref_to_f = False
            pass
      

        symbol_table = build_gdb_symbol_table()
        display_dot (symbol_table.dot_data (only_orders = only_orders,
                                            clones = clones,
                                            only_ref_to_f = only_ref_to_f),
                     filename = "{}/symtab_{:03d}.png".format(self.dirname,
                                                              self.filenum),
                     wait = False)
        self.filenum = self.filenum + 1
        return


ListSymTabRepr()
VisualiseSymTabRepr ()


# Crazy stuff

class SeriesOfSymtabPictures (gdb.Command):
    """Gdb command to visualize the symbol table with dot and feh"""

    class SnapshotBreakpoint(gdb.Breakpoint):
        
        def stop(self):
            from symtab import produce_dot

            tab = build_gdb_symbol_table()
            
            filename = "{}/symtab_{:03d}.png".format(self.cmd.dirname,
                                                     self.cmd.filenum)

            only_orders = self.cmd.only_orders
            clones = self.cmd.clones
            only_ref_to_f = self.cmd.only_ref_to_f

            print("Producing image number {:03}".format(self.cmd.filenum))
            produce_dot (tab.dot_data (only_orders = only_orders,
                                       clones = clones,
                                       only_ref_to_f = True),
                         filename = filename)
            self.cmd.filenum = self.cmd.filenum + 1
            return False
            return False

    def __init__(self):
        gdb.Command.__init__(self, "symtab_film", gdb.COMMAND_USER)
        self.filenum = 1
        self.dirname = "."
        return

    def invoke (self, arg_str, from_tty):
        argv = gdb.string_to_argv(arg_str)

        if len (argv) == 0:
            raise gdb.GdbError ("Provide at least one parameter with the "
                                + "breakpoint specification");
      
        self.bspec = argv[0]

        if "clones" in argv:
            self.clones = True
            pass
        else:
            self.clones = False
            pass

        if "nonames" in argv:
            self.only_orders = True
            pass
        else:
            self.only_orders = False
            pass

        if "onlyreftof" in argv:
            self.only_ref_to_f = True
            pass
        else:
            self.only_ref_to_f = False
            pass
      
        bp = self.SnapshotBreakpoint (self.bspec)
        bp.cmd = self


SeriesOfSymtabPictures ()
