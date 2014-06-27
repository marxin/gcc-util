#!/usr/bin/env python

import os
import sys
import subprocess
import commands
import shutil
import datetime
import multiprocessing
import signal

from optparse import OptionParser

parallelism = multiprocessing.cpu_count()
make_cmd = 'make -j' + str(parallelism)
make_test_cmd = 'make check -k -j' + str(parallelism)

to_cleanup = []

def signal_handler(signum, frame):
  log('Signal interrupt handler called')
  process_cleanup()
  exit(2)

def process_cleanup():
  global to_cleanup

  for i in to_cleanup:
    shutil.rmtree(i)

  to_cleanup = []

def err(message):
  log(message)
  exit(1)

def log(message):
  d = str(datetime.datetime.now())
  print('[%s]: %s' % (d, message))

def archive_git(target_folder, revision):
  target_folder = os.path.join(target_folder, 'gcc_' + revision)
  if not os.path.exists(target_folder):
    os.makedirs(target_folder)

  log('Git archive to: ' + target_folder)
  cmd = 'git archive %s | tar -x -C %s' % (revision, target_folder)
  to_cleanup.append(target_folder)
  r = commands.getstatusoutput(cmd)
  if r[0] != 0:
    err('Could not git archive: ' + r[1])

  r = commands.getstatusoutput('du -h %s | tail -n1' % (target_folder))
  log('Folder size: ' + r[1])

  return target_folder

def prepare_revision(options, revision):
  work_folder = options.folder
  os.chdir(work_folder)

  if options.temp != None:
    work_folder = archive_git(options.temp, revision)
  else:
    log('Git checkout of: ' + revision)
    r = commands.getstatusoutput('git checkout ' + revision)
    if r[0] != 0:
      err('Could not checkout to tested revision')

  return work_folder

def compile_and_test(workdir, configure_cmd):
  os.chdir(workdir)

  objdir = os.path.join(workdir, 'objdir')
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

def extract_logs(workdir, gitdir, revision):
  os.chdir(os.path.join(workdir, 'objdir'))

  logs_folder = os.path.join(gitdir, 'logs', revision)

  if not os.path.exists(logs_folder):
    os.makedirs(logs_folder)

  r = commands.getstatusoutput('_extr_sums ' + logs_folder)
  if r[0] != 0:
    err('Could not extract logs: ' + r[1])

def compare_logs(folder, r1, r2):
  f1 = os.path.join(folder, 'logs', r1)
  os.chdir(f1)

  f2 = os.path.join(folder, 'logs', r2)

  r = commands.getstatusoutput('_compare_sums %s' % (f2))
  if r[0] != 0:
    err('Could not compare logs: ' + r[1])

  return r[1]

signal.signal(signal.SIGINT, signal_handler)

parser = OptionParser()
parser.add_option("-f", "--folder", dest="folder", help="git repository folder")
parser.add_option("-r", "--revision", dest="revision", help="git revision")
parser.add_option("-p", "--parent-revision", dest="parent", help="parent git revision")
parser.add_option("-c", "--checking", action="store_true", dest="checking", default=False, help = "enable checking")
parser.add_option("-b", "--bootstrap", action="store_true", dest="bootstrap", default=False, help = "process bootstrap")
parser.add_option("-l", "--languages", dest="languages", help = "languages")
parser.add_option("-t", "--temp", dest="temp", help = "temporary folder (e.g. /dev/shm)")

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

report_file = os.path.join(options.folder, 'logs', options.revision[:10] + '_' + parent[:10] + '.log')

log('Paralellism: ' + str(parallelism))
log('Report file: ' + report_file)

log('Pulling repository')
r = commands.getstatusoutput('git pull')

if r[0] != 0:
  err('Git has failed')

work_folder = prepare_revision(options, options.revision)

compile_and_test(work_folder, configure_cmd)
extract_logs(work_folder, options.folder, options.revision)

process_cleanup()

work_folder = prepare_revision(options, parent)

compile_and_test(work_folder, configure_cmd)
extract_logs(work_folder, options.folder, parent)

diff = compare_logs(options.folder, options.revision, parent)

with open(report_file, 'w+') as f:
  f.write(diff)

f.close()

process_cleanup()
