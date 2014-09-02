#!/usr/bin/python3

import imp
import sys
import time
import unittest
import re
import diff_match_patch as dmp_module
from functools import *
from itertools import *

imp.reload(dmp_module)
diff = dmp_module.diff_match_patch()

def splitkeepsep(s, sep):
  return reduce(lambda acc, elem: acc[:-1] + [acc[-1] + elem] if elem == sep else acc + [elem], re.split("(%s)" % re.escape(sep), s), [])

class Function:
  def __init__(self, name, mangled, lines):
    self.name = name
    self.mangled = mangled
    self.lines = lines

  def __eq__(self, other):
    if len(self.lines) != len(other.lines):
      return False

    return all(map(lambda x: x[1] == other.lines[x[0]], enumerate(self.lines)))

  @staticmethod
  def split_diff(diffs):
    filtered = []

    for d in diffs:
      if '\n' in d[1]:
        parts = map(lambda x: (d[0], x), splitkeepsep(d[1], '\n'))
        filtered.extend(parts)
      else:
        filtered.append(d)

    return list(filter(lambda x: len(x[1]) > 0, filtered))

  @staticmethod
  def try_fix_source(source_line, target_line, d, src, dst):
    patterns = ['D\.[0-9]+', '_[0-9]+', '<bb [0-9]+>', 'pretmp_[0-9]+', 'prephitmp_[0-9]+']
    new_source_line = source_line

    for pattern in patterns:
      source_matches = list(re.finditer(pattern, source_line))
      target_matches = list(re.finditer(pattern, target_line))

      if len(source_matches) == len(target_matches):
        for (i, value) in enumerate(source_matches):        
          s = source_matches[i].group()
          t = target_matches[i].group()
          tr = None

          if s in d:
            if d[s] != t:
              return None
          else:
            d[s] = t
          tr = d[s]
          new_source_line = new_source_line.replace(str(s), str(tr))
   
    return new_source_line

  def difference(self, other):
    strbuf = ''
    source_text = '\n'.join(self.lines)
    target_text = '\n'.join(other.lines)
    r = diff.diff_lineMode(source_text, target_text, None)
    r = Function.split_diff(r)
    self.diff_result = r

    d = {}
    strbuf = strbuf + ('Name: %s\n' % self.mangled)
    source_i = 0
    target_i = 0

    global_report = False
    last_reported = [-1, -1]

    while len(r) > 0:
      chunk = list(takewhile(lambda x: x[1][-1] != '\n', r))

      if len(chunk) < len(r):
        chunk.append(r[len(chunk)])
     
      source_line = self.lines[source_i]
      target_line = other.lines[target_i]

      if len(chunk) == 1 and chunk[0][0] == 0:
        pass # strbuf = strbuf + chunk[0][1]
      else:
        report = True
        if any(map(lambda x: x[0] <= 0, chunk)) and any(map(lambda x: x[0] >= 0, chunk)):
          new_source_line = Function.try_fix_source(source_line, target_line, d, self, other)
#          strbuf = strbuf + 'new_source_line:' + str(new_source_line) + '\n'
          report = new_source_line == None or new_source_line != target_line
          if new_source_line != None:
            self.lines[source_i] = new_source_line

        if report:
          global_report = True
#          strbuf = strbuf + str(chunk) + '\n'
          if any(map(lambda x: x[0] <= 0, chunk)) and last_reported[0] != source_i:
            strbuf = strbuf + '---' + source_line + '\n'
            last_reported[0] = source_i

          if any(map(lambda x: x[0] >= 0, chunk)) and last_reported[1] != target_i:
            strbuf = strbuf + '+++' + target_line + '\n'
            last_reported[1] = target_i

      # cut the buffer
      r = r[len(chunk):]


#      strbuf = strbuf + 'CHUNK_all:' + str(chunk) + '\n'
      if any(map(lambda x: x[0] <= 0, chunk)) and chunk[-1][1][-1] == '\n' and chunk[-1][0] <= 0:
        source_i = source_i + 1
#        strbuf = strbuf + 'SRC_INCREMENT\n'
#        strbuf = strbuf + 'SRC_LINE_:' + str(self.lines[source_i - 1]) + '\n'

      if any(map(lambda x: x[0] >= 0, chunk)) and chunk[-1][1][-1].endswith('\n') and chunk[-1][0] >= 0:
        target_i = target_i + 1
#        strbuf = strbuf + 'DST_INCREMENT\n'
#        strbuf = strbuf + 'DST_LINE_:' + str(other.lines[target_i - 1]) + '\n'

#    for i in self.diff_result:
#      strbuf = strbuf + str(i) + '\n'

    if global_report:
      print(strbuf)

    return not global_report

  def dump(self):
    print('Name: %s' % self.name)
    print('\n'.join(self.lines))

class DumpFile:
  def __init__(self, text):
    self.lines = text.strip().split('\n')
    self.trim_lines()
    self.parse_functions()

  @staticmethod
  def line_filter(line):
    line = line.strip()
    if line.startswith('Removing basic block'):
      return False

    if line.startswith('#'):
      return False

    if line.strip() == '':
      return False

    return True

  def trim_lines(self):
    self.lines = list(filter(DumpFile.line_filter, self.lines))

  def parse_functions(self):
    self.functions = []

    func = None
    mangled = []
    buff = []
    for i in self.lines:
      if i.startswith(';;'):
        end = i.find('funcdef_no') - 2
        start = i.rfind('(', 0, end) + 1
        mangled.append(i[start:end])
        continue

      if len(i) > 0 and i[0] != '{' and i[0] != '}' and i[0] != ' ' and i[0] != '<':
        if func != None:
          self.functions.append(Function(func, mangled[-2], buff))
          func = i
          buff = []
        else:
          func = i
      else:
        buff.append(i)

    if func != None:
      self.functions.append(Function(func, mangled[-1], buff))

  def compare(self, dump):
    source_functions = {v.name: v for v in self.functions}
    target_functions = {v.name: v for v in dump.functions}

    for f in self.functions:
      if not f.name in target_functions:
        print('Missing in source: %s' % f.name)

    for f in dump.functions:
      if not f.name in source_functions:
        print('Missing in target: %s' % f.name)

    with open("/tmp/tree_diff_source.txt", "w+") as f1:
      with open("/tmp/tree_diff_target.txt", "w+") as f2:
        for f in filter(lambda x: x.name in target_functions, self.functions):
          target = target_functions[f.name]

          r = f == target
          if not r:        
            if not f.difference(target):
              f1.write('Name: ' + f.mangled + '\n')
              f1.write('\n'.join(f.lines) + '\n')
              f2.write('Name: ' + target.mangled + '\n')
              f2.write('\n'.join(target.lines) + '\n')

  def dump(self):
    print('\n'.join(self.lines))

f1 = sys.argv[1]
f2 = sys.argv[2]

d1 = DumpFile(open(f1).read())
d2 = DumpFile(open(f2).read())

d1.compare(d2)

# d1.dump()


# diff = dmp_module.diff_match_patch()
# r = diff.diff_lineMode(lines1, lines2, None)
# print(r)
