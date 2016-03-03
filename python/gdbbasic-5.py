# GDB Python scripts I use in basically all debugging sessions of gcc
# trunk.  Intended also to replace .gdbinit that comes with gcc.

import gdb
from gdb.printing import PrettyPrinter, register_pretty_printer, RegexpCollectionPrettyPrinter

# Basic commands to call internal pretty printers

class CallCompiledPrinter (gdb.Command):
    """Base class to facilitate commands calling internal pretty printers"""

    def __init__(self, command, function, typename = "tree"):
        super (CallCompiledPrinter, self).__init__(command, gdb.COMMAND_DATA,
                                                   gdb.COMPLETE_SYMBOL)
        self.function = function
        self.typename = typename
        return

    def invoke (self, arg_str, from_tty):
        argv = gdb.string_to_argv(arg_str)
        if len (argv) != 1:
            raise gdb.GdbError ("Provide one argument to print");
        try:
            t = gdb.parse_and_eval (argv[0])
        except:
            raise gdb.GdbError ("Could not evaluate %s" % argv[0])
        if t.is_optimized_out:
            raise gdb.GdbError ("Value optimized out")
        self.dont_repeat()
        gdb.execute ("call %s ((%s) 0x%x)" % (self.function, self.typename,
                                            long(t)))
        return

class TreeDebug (CallCompiledPrinter):
    """Call debug_tree on a tree"""

    def __init__(self):
        super (TreeDebug, self).__init__("pt", "debug_tree")
        return

class TreeGenericExpr (CallCompiledPrinter):
    """Call debug_generic_expr on a tree"""

    def __init__(self):
        super (TreeGenericExpr, self).__init__("pge", "debug_generic_expr")
        return

class GimpleDebug (CallCompiledPrinter):
    """Call debug_gimple_stmt on a gimple statement"""

    def __init__(self):
        super (GimpleDebug, self).__init__("pgg", "debug_gimple_stmt", "gimple")
        return

class RtxDebug (CallCompiledPrinter):
    """Call debug_rtx on an rtx"""

    def __init__(self):
        super (RtxDebug, self).__init__("pr", "debug_rtx", "rtx")
        return

class CgnDebug (CallCompiledPrinter):
    """Call debug_cgraph_node on a cgraph_node"""

    def __init__(self):
        super (CgnDebug, self).__init__("pcg", "debug_cgraph_node", "cgraph_node *")
        return



# Vector related stuff

def vec_get_length (gdbval):
    try:
        if long(gdbval) == 0:
            return 0
    except:
        pass

    try:
        gdbval = gdbval["m_vec"]
    except:
        pass

    try:
        if long(gdbval) == 0:
            return 0
    except:
        pass

    pfx = gdbval["m_vecpfx"]
    return int(pfx["m_num"])

def vec_get_item (gdbval, i):
    """Return i-th item in vector represented by gdbval"""
    l = True;
    try:
        l = long(gdbval)
    except:
        pass
    if l == 0:
        raise gdb.GdbError("Cannot access item of NULL vector")
    
    try:
        gdbval = gdbval["m_vec"]
    except:
        pass

    try:
        l = long(gdbval)
    except:
        pass
    if l == 0:
        raise gdb.GdbError("Cannot access item of NULL vector")
    
    if i >= vec_get_length(gdbval):
        raise gdb.GdbError(("Index %i out of vector bounds %i"
                            % (i, vec_get_length(gdbval))))
    return gdbval["m_vecdata"][i]

def vec_iter (gdbval):
    """Return and iterator over vector represented by gdbval"""

    for i in range (vec_get_length (gdbval)):
        yield vec_get_item(gdbval, i)
        pass
    return

class VecGetLength (gdb.Function):
    """Return length of a vector"""

    def __init__ (self):
        super (VecGetLength, self).__init__("vec_len")
        return
    
    def invoke (self, vec):
        return vec_get_length (vec)

class VecGetItem (gdb.Function):
    """Return length of a vector"""

    def __init__ (self):
        super (VecGetItem, self).__init__("vec_item")
        return
    
    def invoke (self, vec, i):
        return vec_get_item (vec, i)

# Tree related stuff

def tree_get_identifier_str (gdbval):
    """Return the identifier string encoded by it"""
    return gdbval['identifier']['id']['str'].string()

def tree_get_decl_name (gdbval):
    """Return tree decl name"""

    decl_name = gdbval['decl_minimal']['name']
    if long(decl_name) == 0:
        return ""
    return tree_get_identifier_str(decl_name)

class TreePrettyPrinter (PrettyPrinter):
    """Pretty printer for TREEs"""

    def __init__ (self):
        super (TreePrettyPrinter, self).__init__("tree",)
        return

    def __call__(self, gdbval):
        if str(gdbval.type.unqualified()) == "tree":
            self.gdbval = gdbval;
            return self
        return None

    def to_string(self):
        if long(self.gdbval) == 0:
            return "NULL_TREE"
        if self.gdbval.is_optimized_out:
            return "<tree optimized out>"
        
        try:
            code = self.gdbval['base']['code']
        except:
            return "<unknown tree 0x%x>" % long(self.gdbval)

        tree_code_name = gdb.parse_and_eval("tree_code_name")
        str_code_name = tree_code_name[long(code)].string()
        result = '<%s 0x%x' % (str_code_name, long(self.gdbval))

        tree_code_type = gdb.parse_and_eval("tree_code_type")
        tclass = long(tree_code_type[code])

        if tclass == 3:  #tcc reference
            result = result + " " + tree_get_decl_name (self.gdbval) +">"
        else:
            result = result + ">"

        return result

# Symbol table related stuff

def symtab_node_name(gdbval):
    """Return node description string in the form of name/symbol_order"""

    if long(gdbval) == 0:
        return ""
    sym = gdbval
    return tree_get_decl_name(sym["decl"])


def symtab_node_string(gdbval):
    """Return node description string in the form of name/symbol_order"""

    if long(gdbval) == 0:
        return "NULL"
    sym = gdbval
    return "%s/%i" % (symtab_node_name(gdbval), sym["order"])

def symtab_get_sym_type(gdbval):
    """Return the type constant of a symbol table node"""
    return long(gdbval["type"])

def symtab_node_is_function(gdbval):
    """Return true if gdbval represents a function"""
    try:
        symtype = symtab_get_sym_type (gdbval)
    except:
        return False
    return symtype == 1
    
def symtab_node_is_variable(gdbval):
    """Return true if gdbval represents a variable"""
    try:
        symtype = symtab_get_sym_type (gdbval)
    except:
        return False
    return symtype == 2

class SymtabNodePrettyPrinter:
    """Pretty printer for symbol table nodes"""

    def __init__(self, gdbval):
        self.gdbval = gdbval
        return

    def to_string(self):
        if long(self.gdbval) == 0:
            return "<symtab_symbol NULL>"

        try:
            sym = self.gdbval
            symtype = long(sym["type"])
        except:
            return "<unknown symbol table node at 0x%x>" % long(self.gdbval)
        if symtype == 0:
            tstr = "symtab_symbol"
        elif symtype == 1:
            tstr = "symtab_function"
        elif symtype == 2:
            tstr = "symtab_variable"
        else:
            return "<bogus symbol table node at 0x%x>" % long(self.gdbval)
            
        return "<%s 0x%x %s>" % (tstr, long(self.gdbval),
                                    symtab_node_string (self.gdbval))

class CgraphEdgePrettyPrinter:
    """Pretty printer for call graph edges"""

    def __init__(self, gdbval):
        self.gdbval = gdbval
        return

    def to_string(self):
        if long(self.gdbval) == 0:
            return "<cgraph_edge NULL>"
        caller_str = symtab_node_string (self.gdbval["caller"])
        result = "<cgraph_edge %s -> " % caller_str
        if long(self.gdbval["indirect_unknown_callee"]) != 0:
            ii = self.gdbval["indirect_info"]
            param_index = long(ii["param_index"])
            if param_index >= 0:
                result += "PARM %i" % param_index
            else:
                result += "UNKNOWN"
                pass
            if long(ii["polymorphic"]) != 0:
                result += " polymorphic"
                pass
            if long(ii["agg_contents"]) != 0:
                result += " aggregate"
                pass
            if long(ii["member_ptr"]) != 0:
                result += " member_ptr"
                pass
            pass
        else:
            result += symtab_node_string (self.gdbval["callee"])
            if long(self.gdbval["inline_failed"]) == 0:
                result += " inlined"
                pass
            if long(self.gdbval["indirect_inlining_edge"]) != 0:
                result += " ii_edge"
                pass
            pass
        result += ">"
        return result
                
class SymtabPrinterDispatcher (PrettyPrinter):
    """Pretty printer dispatcher for symbol table data"""
    def __init__ (self):
        super (SymtabPrinterDispatcher, self).__init__("symtab")
        return

    def __call__(self, gdbval):
        strtype = str(gdbval.type.unqualified())
        if (strtype == "symtab_node_def *" or
            strtype == "cgraph_node *" or
            strtype == "varpool_node *"):
            return SymtabNodePrettyPrinter(gdbval)
        if (strtype == "cgraph_edge *"):
            return CgraphEdgePrettyPrinter(gdbval)
        return None
    
class CgraphNodeCountCallers (gdb.Function):
    """Return number of callers a particular call graph node has."""

    def __init__ (self):
        super (CgraphNodeCountCallers, self).__init__("cgn_count_callers")
        return

    def invoke (self, node):
        e = node["callers"]
        count = 0

        while long(e) != 0:
            count = count + 1
            e = e["next_caller"]
            pass
        return count

class CgraphNodeCountCallees (gdb.Function):
    """Return number of callees a particular call graph node has."""

    def __init__ (self):
        super (CgraphNodeCountCallees, self).__init__("cgn_count_callees")
        return

    def invoke (self, node):
        e = node["callees"]
        count = 0

        while long(e) != 0:
            count = count + 1
            e = e["next_callee"]
            pass
        return count

# ipa-prop stuff

class JumpFunctionPrettyPrinter:
    """Pretty printer for a jump function"""

    def __init__(self, gdbval):
        self.gdbval = gdbval
        return

    def agg_jf_to_string(self):
        r = "\n  Aggregate values:"
        vec = self.gdbval["agg"]["items"]
        for j in vec_iter(vec):
            r += ("\n  offset={:05d} value={}".format(long(j["offset"]),
                                                      j["value"]))
            pass
        return r

    def to_string(self):
        try:
            if long(self.gdbval) == 0:
                return "<ipa_jump_func NULL>"
        except:
            pass

        tp = int(self.gdbval["type"])
        if tp == int(gdb.parse_and_eval("IPA_JF_UNKNOWN")):
            r = "IPA_JF_UNKNOWN"
            pass
        elif tp == int(gdb.parse_and_eval("IPA_JF_KNOWN_TYPE")):
            kt = self.gdbval["value"]["known_type"]
            r = ("IPA_JF_KNOWN_TYPE offset={:d} base_type={}, component_"
                 + "type={}").format(long(kt["offset"]),
                                     kt["base_type"].string,
                                     kt["component_type"])
            pass
        elif tp == int(gdb.parse_and_eval("IPA_JF_CONST")):
            c = self.gdbval["value"]["constant"]
            r = ("IPA_JF_CONST value={}, rdesc=0x{:x}"
                 +" ").format(c["value"], long(c["rdesc"]))
            pass
        elif tp == int(gdb.parse_and_eval("IPA_JF_PASS_THROUGH")):
            ptd = self.gdbval["value"]["pass_through"]
            r = ("IPA_JF_PASS_THROUGH formal_id={:d}, agg_preserved={:d}"
                 + " ").format(int(ptd["formal_id"]),
                               int(ptd["agg_preserved"]))

            opnum = int(ptd["operation"])
            if opnum == int(gdb.parse_and_eval("NOP_EXPR")):
                codenames = gdb.parse_and_eval("tree_code_name")
                opstr = codenames[opnum].string()
                r += "operation={}, operand={}".format(opstr, ptd["operand"]) 
                pass
            pass
        elif tp == int(gdb.parse_and_eval("IPA_JF_ANCESTOR")):
            an = self.gdbval["value"]["ancestor"]
            r = ("IPA_JF_ANCESTOR offset={:d}, type={}, formal_id={:d} "
                 + "agg_preserved={:d}").format(long(an["offset"]),
                                                an["type"], an["formal_id"],
                                                an["agg_preserved"])
            pass
        else:
            r = "UNKNOWN JF TYPE"
            pass

        if long(self.gdbval["agg"]["items"]) != 0:
            r += self.agg_jf_to_string()
            pass

        return r

class IPAPropPrinterDispatcher (PrettyPrinter):
    """Pretty printer dispatcher for ipa-prop data"""
    def __init__ (self):
        super (IPAPropPrinterDispatcher, self).__init__("ipa-prop")
        return

    def __call__(self, gdbval):
        strtype = str(gdbval.type.unqualified())
        if (strtype == "ipa_jump_func"
            or strtype == "ipa_jump_func *"):
            return JumpFunctionPrettyPrinter(gdbval)
        return None


# Set basic breakpoints

def set_basic_breakpoints():
    for i in ["fancy_abort", "internal_error"]:
        found = False
        if gdb.breakpoints():
            for j in gdb.breakpoints():
                if j.location.find(i) >= 0:
                    print ("Breakpoint %i already set in %s (hit %i times)"
                           % (j.number, i, j.hit_count))
                    found = True
                    break
                pass
            pass

        if not found:
            gdb.Breakpoint (i)
            pass
        pass
    return

TreeDebug()
TreeGenericExpr()
GimpleDebug()
RtxDebug()
CgnDebug()

VecGetLength()
VecGetItem()
register_pretty_printer(gdb.current_objfile(), TreePrettyPrinter(), True)
register_pretty_printer(gdb.current_objfile(), SymtabPrinterDispatcher(), True)
    
CgraphNodeCountCallers()
CgraphNodeCountCallees()
register_pretty_printer(gdb.current_objfile(), IPAPropPrinterDispatcher(),
                        True)

set_basic_breakpoints()

gdb.execute("set unwindonsignal on")
gdb.execute("skip file tree.h")
gdb.execute("set check type off")
