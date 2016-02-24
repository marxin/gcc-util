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

class GccTesterError(Exception):
    pass

parallelism = multiprocessing.cpu_count()
make_cmd = 'make -j' + str(parallelism)
make_test_cmd = 'make check -k -j' + str(parallelism)

def tail(message):
  lines = message.split('\n')
  return '\n'.join(lines[-50:])

class GccTester:
    def __init__(self, revision, options):
        self.folder = options.folder
        self.temp = options.temp
        self.messages = []
        self.configure_cmd = ['../configure']
        self.to_cleanup = []
        self.default_options = ['--enable-languages=' + options.languages]

        os.chdir(self.folder)

        self.log('Fetching repository')
        r = commands.getstatusoutput('git fetch --all')

        if r[0] != 0:
            self.err('Git fetch has failed', False)

        self.revision = self.get_sha1_for_revision(revision)
        if options.parent != None:
            self.parent = self.get_sha1_for_revision(options.parent)
        else:
            self.parent = self.get_sha1_for_revision(self.revision + '^')

        self.revision_log_message = self.get_log_message(revision)
        self.parent_log_message = self.get_log_message(self.parent)

        # create folders
        self.tester_folder = os.path.join(self.folder, 'tester')
        self.logs_folder = os.path.join(self.tester_folder, 'logs')
        self.reports_folder = os.path.join(self.tester_folder, 'reports')

        if not os.path.exists(self.logs_folder):
            os.makedirs(self.logs_folder)
        if not os.path.exists(self.reports_folder):
            os.makedirs(self.reports_folder)

        self.report_file = os.path.join(self.reports_folder, self.revision + '_' + self.parent + '.log')

        self.log('Paralellism: ' + str(parallelism))
        self.log('Report file: ' + self.report_file)

    def process_revision(self, revision, configure_cmd):
        self.log('Processing revision: %s' % revision)
        if os.path.exists(os.path.join(self.logs_folder, revision)):
            self.log('Skipping build, already in log cache')
        else:
            work_folder = self.prepare_revision(revision)
            self.compile_and_test(work_folder, configure_cmd)
            self.extract_logs(work_folder, revision)

    def log(self, message, add_time = True):
        s = message
        if add_time:
            d = str(datetime.datetime.now())
            s = '[%s]: %s' % (d, message)
        print(s)

        self.messages += [s]

    def err(self, message, send_email = True):
        self.log('\n' + tail(message))
        if send_email:
            self.send_email(True)
        raise GccTesterError()

    def process_cleanup(self):
        for i in self.to_cleanup:
            shutil.rmtree(i)

        self.to_cleanup = []

    def get_sha1_for_revision(self, revision):
        try:
            return subprocess.check_output(['git', 'rev-parse', revision]).strip()
        except subprocess.CalledProcessError:
            self.err('git rev-parse has failed', False)

    def get_log_message(self, revision):
        return subprocess.check_output(['git', 'log', '-n1', revision]).strip()

    def send_email(self, failure = False):
        msg = MIMEMultipart("alternative")

        text = '\n'.join(self.messages)
        text = MIMEText(text, "plain", "utf-8")
        msg.attach(text)

        sender = 'mliska+tester@suse.cz'
        recipient = 'mliska@suse.cz'

        msg['Subject'] = 'GCC tester email: %s (%s vs. %s)' % ('FAILURE' if failure else 'SUCCESS', self.revision, self.parent)
        msg['From'] = sender
        msg['To'] = recipient

        s = smtplib.SMTP('localhost')
        s.sendmail(sender, [recipient], msg.as_string())
        s.quit()

    def archive_git(self, revision):
        target_folder = os.path.join(self.folder, 'gcc_' + revision)
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)

        self.log('Git archive to: ' + target_folder)
        cmd = 'git archive %s | tar -x -C %s' % (revision, target_folder)
        self.to_cleanup.append(target_folder)
        r = commands.getstatusoutput(cmd)
        if r[0] != 0:
            self.err('Could not git archive: ' + r[1])

        r = commands.getstatusoutput('du -h %s | tail -n1' % (target_folder))
        self.log('Folder size: ' + r[1])

        return target_folder

    def prepare_revision(self, revision):
      os.chdir(self.folder)
      work_folder = self.folder

      if self.temp != None:
        work_folder = self.archive_git(revision)
      else:
        self.log('Git checkout of: ' + revision)
        r = commands.getstatusoutput('git checkout ' + revision)
        if r[0] != 0:
          self.err('Could not checkout to tested revision')

      return work_folder

    def compile_and_test(self, workdir, configure_cmd):
        os.chdir(workdir)

        objdir = os.path.join(workdir, 'objdir')
        if os.path.exists(objdir):
            shutil.rmtree(objdir)

        os.makedirs(objdir)
        self.log('Creating: %s' % objdir)

        self.log('Changing chroot to folder:' + objdir)
        os.chdir(objdir)

        self.log('Configure process has been started')
        r = commands.getstatusoutput(' '.join(configure_cmd))
        if r[0] != 0:
            self.err('Could not configure GCC: ' + r[1])

        self.log('Build process has been started')
        r = commands.getstatusoutput(make_cmd)

        if r[0] != 0:
            self.err('Could not build GCC: ' + r[1])

        self.log('Test process has been started')
        r = commands.getstatusoutput(make_test_cmd)

    def extract_logs(self, workdir, revision):
        objdir = os.path.join(workdir, 'objdir')
        os.chdir(objdir)

        logs_folder = os.path.join(self.logs_folder, revision)
        if not os.path.exists(logs_folder):
            os.makedirs(logs_folder)

        r = commands.getstatusoutput('_extr_sums ' + logs_folder)
        if r[0] != 0:
            self.err('Could not extract sums: ' + r[1])

        os.chdir(os.path.join(objdir, 'gcc', 'testsuite'))

        r = commands.getstatusoutput('_extr_logs ' + logs_folder)
        if r[0] != 0:
            self.err('Could not extract logs: ' + r[1])

        os.chdir(objdir)

    def compare_logs(self, r1, r2):
        f1 = os.path.join(self.logs_folder, r1)
        os.chdir(f1)

        f2 = os.path.join(self.logs_folder, r2)

        r = commands.getstatusoutput('_compare_sums %s' % (f2))
        if r[0] != 0:
            self.err('Could not compare logs: ' + r[1])

        return r[1]

    def run(self):
        # core of the script
        self.process_revision(self.revision, self.configure_cmd + self.default_options)
        self.process_cleanup()
        self.process_revision(self.parent, self.configure_cmd + self.default_options + ['--disable-bootstrap', '--enable-checking=release'])

        diff = self.compare_logs(self.revision, self.parent)

        with open(self.report_file, 'w+') as f:
          f.write(diff)

        f.close()

        self.process_cleanup()

        self.log('Commit log', False)
        self.log(self.revision_log_message, False)
        self.messages += ['Compare logs', diff]
        self.send_email(False)

gcc = None

def signal_handler(signum, frame):
    global gcc
    gcc.log('Signal interrupt handler called')
    gcc.process_cleanup()
    exit(1)

signal.signal(signal.SIGINT, signal_handler)

parser = OptionParser()
parser.add_option("-f", "--folder", dest="folder", help="git repository folder")
parser.add_option("-r", "--revision", dest="revision", help="git revision")
parser.add_option("-p", "--parent-revision", dest="parent", help="parent git revision")
parser.add_option("-t", "--temp", dest="temp", help = "temporary folder (e.g. /dev/shm)")
parser.add_option("-l", "--languages", dest="languages", default = 'all', help = "specify languages that should be tested")

(options, args) = parser.parse_args()

if not options.folder:
  parser.error('folder not specified')

if not options.revision:
  parser.error('revision not specified')

if not os.path.exists(options.folder) or not os.path.isdir(options.folder):
  err('git folder does not exist')

revisions = options.revision.split(',')

for (i, r) in enumerate(revisions):
    try:
        gcc = GccTester(r, options)
        gcc.log('Processing revision: %d/%d' % (i + 1, len(revisions)))
        gcc.run()
    except GccTesterError as e:
        pass
