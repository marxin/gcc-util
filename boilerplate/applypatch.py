#!/usr/bin/env python

from __future__ import print_function
import os
import os.path
import sys
import subprocess
import commands
import shutil
import datetime
import multiprocessing
import signal
import argparse
import datetime
import time
from itertools import *

def strip_array(condition, lines):
  start = len(list(takewhile(condition, lines)))
  end = len(list(takewhile(condition, reversed(lines))))
  return lines[start:len(lines) - end]

class Patch:
  @staticmethod
  def parse_lines(text, args):
      results = []
      lines = []

      f = None
      for line in text:
	if line.endswith('ChangeLog:'):
	  if f != None:
	    results.append(ChangeLogEntry(f, lines, args))
	  f = line.rstrip(':')	  
	  lines = []
	else:
	  lines.append(line)

      if f != None:
	results.append(ChangeLogEntry(f, lines, args))

      return results

  def __init__(self, args):
    self.patch_path = args.file
    self.subject =  None
    text = list(takewhile(lambda x: x.rstrip() != '---', [x.rstrip() for x in open(args.file).readlines()]))
    s = 'Subject:'
    subjects = [x for x in text if x.startswith(s)]
    if len(subjects):
      self.subject = self.trim_subject(subjects[0][len(s):].strip())

    if args.message:
      self.subject = args.message

    self.entries = Patch.parse_lines(text, args)
    self.directory = args.directory

  def trim_subject (self, subject):
    i = subject.rfind(']')
    if i != -1:
      subject = subject[(i + 1):].strip()

    return subject

  def add_entries(self):
    for entry in self.entries:
      entry.add_entry(self.directory)

  def create_svn_log(self):
    bodies = '\n'.join(map(lambda x: x.get_body(), self.entries))

    fullname = os.path.join(self.directory, 'commit-msg.tmp')
    with open(fullname, 'w') as log:
      h = self.subject or self.entries[0].get_header()
      print(h, file = log)
      print('', file = log)
      print(bodies, file = log)

    print('SVN commit file has been created: %s' % fullname)

  def apply_patch(self):
    input = open(self.patch_path)
    subprocess.check_output(['patch', '-p1'], stdin = input)

class ChangeLogEntry:
  def __init__(self, file, lines, args):
    self.file = file

    lines = strip_array(lambda x: x.strip() == '', lines)
    first = lines[0]
    tokens = first.split(' ')
    self.lines = strip_array(lambda x: x.strip() == '', lines[1:])
    self.date = tokens[0]
    self.email = args.email or tokens[-1]
    self.username = args.username or first[first.find(' '):first.rfind(' ')].strip()

  def get_header(self):
    now = time.strftime('%Y-%m-%d')
    return '%s  %s  %s' % (now, self.username, self.email)

  def get_body(self):
    return '\n'.join(self.lines)

  def add_entry(self, folder):
    filename = os.path.join(folder, self.file)
    with open(filename, 'r') as original:
      text = original.read()
      with file(filename, 'w') as f:        
        print(self.get_header(), file = f)
	print(file = f)
	print(self.get_body(), file = f)
	print(file = f)
	f.write(text)

    print('ChangeLog entry added: %s' % self.file)

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--directory", dest="directory", help="SVN repository directory", default = os.getcwd())
parser.add_argument("-f", "--file", dest="file", help="file with patch", required = True)
parser.add_argument("-u", "--username", dest="username", help = "commit username")
parser.add_argument("-e", "--email", dest="email", help = "commit email address")
parser.add_argument("-m", "--message", dest="message", help = "commit message header")
parser.add_argument('-s', dest='skip_patch', action='store_true')

args = parser.parse_args()
patch = Patch(args)

if not args.skip_patch:
    patch.apply_patch()

patch.add_entries()
patch.create_svn_log()
