#!/usr/bin/env python

import os
import sys
import subprocess
import commands
import shutil
import datetime

from optparse import OptionParser

parallelism = 9
make_cmd = 'make -j' + str(parallelism)
make_test_cmd = 'make check -k -j' + str(parallelism)

def err(message):
  log(message)
  exit(1)

def log(message):
  d = str(datetime.datetime.now())
  print('[%s]: %s' % (d, message))

def compile_and_test(folder, configure_cmd):
  os.chdir(folder)

  objdir = os.path.join(folder, 'objdir')
  if os.path.exists(objdir):
    shutil.rmtree(objdir)

  os.mkdir(objdir)
  os.chdir(objdir)

  log('Configure process has been started')
  r = commands.getstatusoutput(configure_cmd)
  if r[0] != 0:
    err('Could not configure GCC: ' + r[1])

  log('Build process has been started')
  r = commands.getstatusoutput(make_cmd)

  if r[0] != 0:
    err('Could not build GCC: ' + r[1])

  log('Test process has been started')
  r = commands.getstatusoutput(make_test_cmd)

def extract_logs(folder, revision):
  os.chdir(os.path.join(folder, 'objdir'))

  logs_folder = os.path.join(folder, 'logs', revision)

  if not os.path.exists(logs_folder):
    os.makedirs(logs_folder)

  r = commands.getstatusoutput('_extr_sums ' + logs_folder)
  if r[0] != 0:
    err('Could not extract logs: ' + r[1])

def compare_logs(folder, r1, r2):
  f1 = os.path.join(folder, 'logs', r1)
  f2 = os.path.join(folder, 'logs', r2)

  r = commands.getstatusoutput('_compare_sums %s %s' % (f1, f2))
  if r[0] != 0:
    err('Could not compare logs: ' + r[1])

  return r[1]

parser = OptionParser()
parser.add_option("-f", "--folder", dest="folder", help="git repository folder")
parser.add_option("-r", "--revision", dest="revision", help="git revision")
parser.add_option("-p", "--parent-revision", dest="parent", help="parent git revision")
parser.add_option("-c", "--checking", action="store_true", dest="checking", default=False, help = "enable checking")
parser.add_option("-b", "--bootstrap", action="store_true", dest="bootstrap", default=False, help = "process bootstrap")
parser.add_option("-l", "--languages", dest="languages", help = "languages")

(options, args) = parser.parse_args()

if not options.folder:
  parser.error('folder not specified')

if not options.revision:
  parser.error('revision not specified')

if not os.path.exists(options.folder) or not os.path.isdir(options.folder):
  err('git folder does not exist')

# build of configure command line
configure_cmd = '../configure'

if not options.bootstrap:
  configure_cmd = configure_cmd + ' --disable-bootstrap'

if not options.checking:
  configure_cmd = configure_cmd + ' --enable-checking=release'

if options.languages != None:
  configure_cmd = configure_cmd + ' --enable-languages=' + options.languages

log('Built configure options: ' + configure_cmd)

os.chdir(options.folder)

r = commands.getstatusoutput('git show ' + options.revision)

if r[0] != 0:
  err('Git revision does not exist')

r = commands.getstatusoutput('git rev-parse ' + options.revision + '^')

if r[0] != 0:
  err('Git revision of parent cannot be loaded')

parent = r[1]

if options.parent != None:
  parent = options.parent

r = commands.getstatusoutput('git checkout ' + options.revision)
if r[0] != 0:
  err('Could not checkout to tested revision')

compile_and_test(options.folder, configure_cmd)
extract_logs(options.folder, options.revision)

r = commands.getstatusoutput('git checkout ' + parent)
if r[0] != 0:
  err('Could not checkout to parent revision ' + parent)

compile_and_test(options.folder, configure_cmd)
extract_logs(options.folder, parent)

diff = compare_logs(options.folder, options.revision, parent)
log(diff)
