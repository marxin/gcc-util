#!/usr/bin/env python

import os
import sys
import subprocess
import commands
import shutil
import datetime
import signal

from optparse import OptionParser

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class GccTesterError(Exception):
    pass

ignored = ['guality/']

def tail(message):
  lines = message.split('\n')
  return '\n'.join(lines[-500:])

class GccTester:
    def __init__(self, revision, options):
        self.original_revision = revision
        self.folder = options.folder
        self.temp = options.temp
        self.parallelism = options.parallelism
        self.messages = []
        self.configure_cmd = ['../configure']
        self.to_cleanup = []
        self.default_options = ['--enable-languages=' + options.languages]
        self.extra_configuration = options.extra_configuration.split(',') if options.extra_configuration != None else []

        os.chdir(self.folder)

        self.log('Fetching repository')
        r = commands.getstatusoutput('git fetch --all')

        if r[0] != 0:
            self.err('Git fetch has failed', False)

        self.revision = self.get_sha1_for_revision(revision)

        self.revision_log_message = self.get_log_message(revision)
        self.log('Paralellism: ' + str(self.parallelism))

    def process_revision(self, revision, configure_cmd):
        self.log('Processing revision: %s' % revision)
        work_folder = self.prepare_revision(revision)
        self.compile_and_test(work_folder, configure_cmd)

    def log(self, message, add_time = True):
        s = message
        if add_time:
            d = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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

    def send_email(self, failure = False, failed_tests = 0):
        msg = MIMEMultipart("alternative")

        text = '\n'.join(self.messages)
        text = MIMEText(text, "plain", "utf-8")
        msg.attach(text)

        sender = 'mliska+tester@foxlink.cz'
        recipient = 'mliska@suse.cz'

        revision = self.original_revision.split('/')[-1]
        subject = '%s: %s' % (revision, 'FAILURE' if failure else 'SUCCESS')
        if not failure and failed_tests:
            subject += ' (%d tests failed)' % failed_tests

        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient

        s = smtplib.SMTP('localhost')
        s.sendmail(sender, [recipient], msg.as_string())
        s.quit()

    def archive_git(self, revision):
        target_folder = os.path.join(self.temp, 'gcc_' + revision)
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

      assert self.temp != None
      return self.archive_git(revision)

    def compile_and_test(self, workdir, configure_cmd):
        os.chdir(workdir)

        objdir = os.path.join(workdir, 'objdir')
        if os.path.exists(objdir):
            shutil.rmtree(objdir)

        os.makedirs(objdir)
        self.log('Creating: %s' % objdir)

        self.log('Changing chroot to folder:' + objdir)
        os.chdir(objdir)

        if options.fast:
            configure_cmd.append('--disable-libgomp')

        self.log('Configure process has been started')
        r = commands.getstatusoutput(' '.join(configure_cmd))
        if r[0] != 0:
            self.err('Could not configure GCC: ' + r[1])

        self.log('Build process has been started')
        make_cmd = 'nice make -j' + str(self.parallelism)
        if options.fast:
            make_cmd += ' STAGE1_CFLAGS="-O2"'

        r = commands.getstatusoutput(make_cmd)

        if r[0] != 0:
            self.err('Could not build GCC: ' + r[1])

        self.log('Test process has been started')

        make_test_cmd = 'nice make check -k -j' + str(self.parallelism)
        r = commands.getstatusoutput(make_test_cmd)

    def report_failures(self):
        self.log('Running find in: %s' % os.path.abspath('.'))
        r = subprocess.check_output("find gcc/testsuite/ -name '*.log' | xargs cat", shell = True).decode('utf8', 'ignore')
        lines = r.split('\n')

        failures = sorted([x for x in lines if x.startswith('FAIL')])
        known_failures = [x for x in failures if any([y in x for y in ignored])]
        failures = [x for x in failures if not any([y in x for y in ignored])]
        xfail_count = len([x for x in lines if x.startswith('XFAIL')])
        pass_count = len([x for x in lines if x.startswith('PASS')])

        self.log('PASS count: %d' % pass_count)
        self.log('XFAIL count: %d' % xfail_count)
        self.log('FAIL count: %d' % len(failures))
        self.messages += ['=== FAILURES ===', '\n'.join(failures)]
        self.messages += ['\n\nKnown false FAIL count: %d' % len(known_failures)]
        self.messages += ['=== FALSE positive failures ===', '\n'.join(known_failures)]

        if options.verbose:
            print('\n=== FAILURES ===\n' +'\n'.join(failures))

        return failures

    def run(self):
        # core of the script
        self.process_revision(self.revision, self.configure_cmd + self.default_options + self.extra_configuration)

        self.log('Commit log', False)
        self.log(self.revision_log_message, False)
        failures = self.report_failures()
        self.process_cleanup()
        self.send_email(False, len(failures))

gcc = None

def signal_handler(signum, frame):
    global gcc
    gcc.log('Signal interrupt handler called')
    gcc.process_cleanup()
    exit(1)

signal.signal(signal.SIGINT, signal_handler)

parser = OptionParser()
parser.add_option("-f", "--folder", dest="folder", help="git repository folder")
parser.add_option("-r", "--revisions", dest="revision", help="git revisions")
parser.add_option("-t", "--temp", dest="temp", help = "temporary folder (e.g. /dev/shm)")
parser.add_option("-l", "--languages", dest="languages", default = 'all', help = "specify languages that should be tested")
parser.add_option("-e", "--extra-configuration", dest="extra_configuration", help = "extra configure options, separated by comma")
parser.add_option("-x", "--fast", action = 'store_true', help = "Build stage1 compiler with -O2")
parser.add_option("-v", "--verbose", action = 'store_true', help = "Verbose error reporting")
parser.add_option("-j", "--parallelism", type = int, help = "Number of cores to be used")

(options, args) = parser.parse_args()

if not options.folder:
  parser.error('folder not specified')

if not options.revision:
  parser.error('revision not specified')

if not options.temp:
  parser.error('temp not specified')

if not options.parallelism:
  parser.error('parallelism not specified')

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
