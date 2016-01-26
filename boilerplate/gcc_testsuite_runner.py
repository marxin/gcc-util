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

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

parallelism = multiprocessing.cpu_count()
make_cmd = 'make -j' + str(parallelism)
make_test_cmd = 'make check -k -j' + str(parallelism)

to_cleanup = []
all_messages = []

def signal_handler(signum, frame):
  log('Signal interrupt handler called')
  process_cleanup()
  exit(2)

def process_cleanup():
  global to_cleanup

  for i in to_cleanup:
    shutil.rmtree(i)

  to_cleanup = []

def tail(message):
  lines = message.split('\n')
  return '\n'.join(lines[-50:])

def err(message):
  global revision
  global parent
  log('\n' + tail(message))
  send_email(all_messages, revision, parent, True)
  exit(1)

def log(message, add_time = True):
  s = message
  if add_time:
    d = str(datetime.datetime.now())
    s = '[%s]: %s' % (d, message)
  print(s)
  global all_messages
  all_messages += [s]

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

  os.makedirs(objdir)
  log('Creating: %s' % objdir)

  log('Changing chroot to folder:' + objdir)
  os.chdir(objdir)

  log('Configure process has been started')
  r = commands.getstatusoutput(' '.join(configure_cmd))
  if r[0] != 0:
    err('Could not configure GCC: ' + r[1])

  log('Build process has been started')
  r = commands.getstatusoutput(make_cmd)

  if r[0] != 0:
    err('Could not build GCC: ' + r[1])

  log('Test process has been started')
  r = commands.getstatusoutput(make_test_cmd)

def extract_logs(workdir, logs_root, revision):
  objdir = os.path.join(workdir, 'objdir')
  os.chdir(objdir)

  logs_folder = os.path.join(logs_root, revision)

  if not os.path.exists(logs_folder):
    os.makedirs(logs_folder)

  r = commands.getstatusoutput('_extr_sums ' + logs_folder)
  if r[0] != 0:
    err('Could not extract sums: ' + r[1])

  os.chdir(os.path.join(objdir, 'gcc', 'testsuite'))

  r = commands.getstatusoutput('_extr_logs ' + logs_folder)
  if r[0] != 0:
    err('Could not extract logs: ' + r[1])

  os.chdir(objdir)

def compare_logs(logs_folder, report_folder, r1, r2):
  f1 = os.path.join(logs_folder, r1)
  os.chdir(f1)

  f2 = os.path.join(logs_folder, r2)

  r = commands.getstatusoutput('_compare_sums %s' % (f2))
  if r[0] != 0:
    err('Could not compare logs: ' + r[1])

  return r[1]

def get_sha1_for_revision(revision):
    return subprocess.check_output(['git', 'rev-parse', revision]).strip()

def get_log_message(revision):
    return subprocess.check_output(['git', 'log', '-n1', revision]).strip()

def send_email(messages, revision, parent, failure = False):
    msg = MIMEMultipart("alternative")

    text = '\n'.join(messages)
    text = MIMEText(text, "plain", "utf-8")
    msg.attach(text)

    sender = 'mliska+tester@suse.cz'
    recipient = 'mliska@suse.cz'

    msg['Subject'] = 'GCC tester email: %s (%s vs. %s)' % ('FAILURE' if failure else 'SUCCESS', revision, parent)
    msg['From'] = sender
    msg['To'] = recipient

    s = smtplib.SMTP('localhost')
    s.sendmail(sender, [recipient], msg.as_string())
    s.quit()

signal.signal(signal.SIGINT, signal_handler)

parser = OptionParser()
parser.add_option("-f", "--folder", dest="folder", help="git repository folder")
parser.add_option("-r", "--revision", dest="revision", help="git revision")
parser.add_option("-p", "--parent-revision", dest="parent", help="parent git revision")
parser.add_option("-t", "--temp", dest="temp", help = "temporary folder (e.g. /dev/shm)")

(options, args) = parser.parse_args()

if not options.folder:
  parser.error('folder not specified')

if not options.revision:
  parser.error('revision not specified')

if not os.path.exists(options.folder) or not os.path.isdir(options.folder):
  err('git folder does not exist')

# build of configure command line
configure_cmd = ['../configure']

# TODO: remove
configure_cmd += ['--disable-bootstrap', '--enable-checking=release', '--enable-languages=c,c++']

os.chdir(options.folder)

log('Fetching repository')
r = commands.getstatusoutput('git fetch --all')

if r[0] != 0:
  err('Git fetch has failed')

revision = get_sha1_for_revision(options.revision)
parent = get_sha1_for_revision(options.revision + '^')

revision_log_message = get_log_message(revision)
parent_log_message = get_log_message(parent)

if options.parent != None:
  parent = get_sha1_for_revision(options.parent)

# create folder
root = os.path.join(options.folder, 'tester')
logs_folder = os.path.join(root, 'logs')
reports_folder = os.path.join(root, 'reports')

if not os.path.exists(logs_folder):
    os.makedirs(logs_folder)

report_file = os.path.join(reports_folder, revision + '_' + parent + '.log')

log('Paralellism: ' + str(parallelism))
log('Report file: ' + report_file)

work_folder = prepare_revision(options, revision)

compile_and_test(work_folder, configure_cmd)
extract_logs(work_folder, logs_folder, revision)

process_cleanup()

work_folder = prepare_revision(options, parent)

compile_and_test(work_folder, configure_cmd + ['--disable-bootstrap', '--enable-checking=release'])
extract_logs(work_folder, options.folder, parent)

diff = compare_logs(logs_folder, reports_folder, revision, parent)

with open(report_file, 'w+') as f:
  f.write(diff)

f.close()

process_cleanup()

log('Commit log', False)
log(revision_log_message, False)
send_email(all_messages + [diff], revision, parent, False)
