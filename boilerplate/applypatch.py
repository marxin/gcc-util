#!/usr/bin/env python3

from __future__ import print_function
import os
import os.path
import sys
import subprocess
import shutil
import datetime
import multiprocessing
import signal
import argparse
import datetime
import time
import tempfile
import re

from itertools import *

username = 'Martin Liska'
email = 'mliska@suse.cz' 
pr_regex = re.compile('.*PR [a-z\-\+]+\/([0-9]+).*')

parser = argparse.ArgumentParser()
parser.add_argument('file', help = 'File with patch')
parser.add_argument("-d", "--directory", dest="directory", help="GIT repository directory", default = os.getcwd())
parser.add_argument("-b", "--branch", dest="branch", help = "GIT branch name")
parser.add_argument("--backport", action = 'store_true', help = "Backport from mainline")
parser.add_argument('--dry-run', action='store_true')
parser.add_argument("-c", "--co-author", help = "Add Co-Authored-By note to git commit")

args = parser.parse_args()

def strip_array(condition, lines):
  start = len(list(takewhile(condition, lines)))
  end = len(list(takewhile(condition, reversed(lines))))
  return lines[start:len(lines) - end]

def get_today_timestamp():
    return datetime.datetime.now().strftime('%Y-%m-%d')

class ChangeLogEntry:
  def __init__(self, file, lines):
    self.file = file
    lines = list(dropwhile(lambda x: x == '', lines))
    self.lines = list(reversed(list(dropwhile(lambda x: x == '', reversed(lines)))))

    if args.branch != None:
        self.file += '.' + args.branch

    assert len(self.lines) > 2
    assert self.lines[0].startswith('20')

    if args.backport:
        header_lines = ['\t' + x for x in takewhile(lambda x: x != '', self.lines)]

        # skip header and also one empty line
        self.lines = self.lines[len(header_lines) + 1:]
        l = '%s  %s  <%s>' % (get_today_timestamp(), username, email)
        to_add = [l, '', '\tBackport from mainline'] + header_lines + ['']
        self.lines = to_add + self.lines
    else:
        # update to current date
        h = self.lines[0]
        h = get_today_timestamp() + h[h.find(' '):]
        self.lines[0] = h

  def get_body(self):
    return '\n'.join(self.lines)

  def get_body_without_datetime(self):
      return '\n'.join(self.lines[2:])

  def add_entry(self, folder):
    filename = os.path.join(folder, self.file)
    with open(filename, 'r') as original:
      text = original.read()
      with open(filename, 'w') as f:
        print(self.get_body(), file = f)
        print(file = f)
        f.write(text)

    print('ChangeLog entry added: %s' % self.file)

class Patch:
    @staticmethod
    def parse_lines(lines):
        changelog_entries = []

        # skip all empty lines at the beginning
        lines = list(dropwhile(lambda x: x == '', lines))

        # iterate over ChangeLog files
        while len(lines) > 0:
            file_name = lines[0]
            assert file_name.endswith('ChangeLog:')
            lines = lines[1:]
            chunk = list(takewhile(lambda x: not x.endswith('ChangeLog:'), lines))
            changelog_entries.append(ChangeLogEntry(file_name.rstrip(':'), chunk))
            lines = lines[len(chunk):]

        return changelog_entries

    def parse_add_and_removed_files(self, lines):
        f = lambda x: x.split(' ')[-1][2:]
        for i, l in enumerate(lines):
            if l.startswith('new file mode'):
                self.added_files.append(f(lines[i - 1]))
            elif l.startswith('deleted file mode'):
                self.removed_files.append(f(lines[i - 1]))

    def __init__(self, args):
        self.patch_path = args.file
        self.temp_patch_file = None
        self.entries = []
        self.added_files = []
        self.removed_files = []
        self.prs = set()

        lines = [x.rstrip() for x in open(args.file).readlines()]
        lines = list(dropwhile(lambda x: not x.startswith('Subject:'), lines))
        self.parse_add_and_removed_files(lines)

        subject_lines = list(takewhile(lambda x: x != '', lines))
        self.set_subject(subject_lines)
        lines = lines[len(subject_lines):]

        text = list(takewhile(lambda x: x != '---', lines))
        self.entries = Patch.parse_lines(text)

        self.directory = args.directory

    def set_subject(self, subject_lines):
        subject = ''.join(subject_lines)
        i = subject.rfind(']')
        if i != -1:
            subject = subject[(i + 1):].strip()

        # parse PR
        result = pr_regex.match(subject)
        if result != None:
            self.prs.add(int(result.groups(1)[0]))

        self.subject = subject

    def verify(self):
        r = True
        # parse all new tests whether they are named pr*.*
        for entry in self.entries:
            for l in entry.lines:
                result = re.match('.*[pP][rR]([0-9]+)[^:]*: New test\.', l)
                if result != None:
                    self.prs.add(int(result.groups(1)[0]))

        # verify entries
        for entry in self.entries:
            found = set()
            for l in entry.lines:
                result = pr_regex.match(l)
                if result != None:
                    found.add(int(result.groups(1)[0]))

            if len(self.prs) > len(found):
                r = False
                print('Missing PR entries for %s: ' % (entry.file), end = '')
                for pr in self.prs:
                    if not pr in found:
                        print('PR%d ' % pr, end = '')

                print()

        return r

    def add_entries(self):
        for entry in self.entries:
            entry.add_entry(self.directory)

    def create_git_log(self):
        bodies = '\n'.join(map(lambda x: x.get_body_without_datetime(), self.entries))

        fullname = os.path.join(self.directory, 'commit-msg.tmp')
        with open(fullname, 'w') as log:
            print(self.subject.replace('Subject: ', ''), file = log)
            print('', file = log)
            print(bodies, file = log)

            if args.co_author:
                print('\nCo-Authored-By: %s' % args.co_author, file=log)

        subprocess.check_output('git commit -a -F %s' % fullname, shell = True)

    def apply_patch(self, dry_run = False):
        f = self.temp_patch_file if self.temp_patch_file != None else self.patch_path
        args = ['patch', '-p1', '-f']

        print('Apply patch:')
        with open(f) as input:
            r = subprocess.call(args + ['--dry-run'], stdin = input)
            if r != 0:
                print('Dry run of patch application has failed!')
                return False

        print()
        if not dry_run:
            with open(f) as input:
                subprocess.check_output(args, stdin = input)

            return True

    def manipulate_git(self):
        if len(self.added_files) > 0:
            print('Adding files:')
            for f in self.added_files:
                subprocess.check_output(['git', 'add', os.path.join(self.directory, f)])
                print(f)
            print()

        if len(self.removed_files) > 0:
            print('Removing files:')
            for f in self.removed_files:
                subprocess.check_output(['git', 'rm', os.path.join(self.directory, f)])
                print(f)
            print()

patch = Patch(args)

if not args.dry_run:
    if not patch.verify():
        exit(2)
    if not patch.apply_patch():
        exit(1)
    patch.add_entries()
    patch.manipulate_git()
    patch.create_git_log()
else:
    patch.apply_patch(True)
    patch.verify()
    for entry in patch.entries:
        print(entry.file)
        print(entry.get_body())
