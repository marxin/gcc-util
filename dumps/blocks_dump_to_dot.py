#!/usr/bin/env python3

import re
import sys

def trim_line(line):
    return line.strip(';;').strip(' ').strip()

class BasicBlock:
    def __init__(self, name, depth, count, freq):
        self.name = name
        self.extra = ''
        self.depth = int(depth)
        self.count = int(count)
        self.freq = int(freq)
        self.color = 'white'
        self.scale = -1.0

    def print(self):
        print('BB %s, depth: %d, freq: %d' % (self.name, self.depth, self.freq))

class Edge:
    def __init__(self, src, dst, freq, flags):
        self.src = src
        self.dst = dst
        self.freq = float(freq)

        self.flag = ''
        for f in flags.split(','):
            if f == 'FALSE_VALUE':
                self.flag = 'false'
            elif f == 'TRUE_VALUE':
                self.flag = 'true'

    def get_color(self):
        if self.flag == 'false':
            return 'red'
        elif self.flag == 'true':
            return 'blue'
        else:
            return 'black'

class Loop:
    def __init__(self, lines):
        lines = list(map(lambda x: trim_line(x), lines))
        assert len(lines) == 4
        self.number = lines[0].split(' ')[-1]
        l2 = lines[1].replace(',', '').split(' ')
        self.header = l2[1]
        self.latch = l2[3]
        l3 = lines[2].replace(',', '').split(' ')
        self.depth = int(l3[1])
        self.nodes = lines[3].split(' ')[1:]

last_bb = None
bbs = []
bb_dict = {}
edges = []
loops = []

in_succ = False

bb_re = 'basic block ([0-9]+), loop depth ([0-9]+), count ([0-9]+), freq ([0-9]+).*'
edge_re = '([0-9]+) \[(.*)\%].*\((.*)\)'

lines = open(sys.argv[1]).readlines()
for i, line in enumerate(lines):
    if not line.startswith(';;'):
        in_succ = False
        continue

    line = trim_line(line)
    m = re.match(bb_re, line)
    if m != None:
        bb = BasicBlock(m.group(1), m.group(2), m.group(3), m.group(4))
        bbs.append(bb)
        bb_dict[bb.name] = bb
        last_bb = bb
    elif line.startswith('succ:') or in_succ:
        in_succ = True
        line = line.strip('succ:').strip(' ')        
        m2 = re.match(edge_re, line)
        if m2 != None:
            e = Edge(last_bb.name, m2.group(1), m2.group(2), m2.group(3))
            edges.append(e)
    elif line.startswith('Loop'):
        loops.append(Loop(lines[i:i+4]))

# set interesting loop informations
for l in loops:
    if not l.header in bb_dict or not l.latch in bb_dict:
        continue
    header = bb_dict[l.header]
    header.color = 'yellow'
    header.extra = ' (loop %s)' % l.number
    bb_dict[l.latch].color = 'green'

    for node in l.nodes:
        n = bb_dict[node]
        if header.freq != 0 and n.scale == -1.0:
            n.scale = n.freq / header.freq

print('digraph G { node [shape=box, fontsize=10, height=0.2]; edge [color=gray30,fontsize=10]')

for bb in bbs:
    print ('\t"%s"[label="BB %s (depth: %d, count: %d)%s\\n(freq: %d, scale: %.2f)", fillcolor=%s, style=filled]'
        % (bb.name, bb.name, bb.depth, bb.count, bb.extra, bb.freq, bb.scale, bb.color))

print("\n\tnode [shape=ellipse];\n")

for e in edges:
    print('\t"%s" -> "%s" [color="%s", label="%.2f"];' % (e.src, e.dst, e.get_color(), e.freq))

print('}')
