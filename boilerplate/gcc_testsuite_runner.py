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
parallelism_limit = 60

# Limit due to gcc112 machine
if parallelism > parallelism_limit:
    parallelism = parallelism_limit

make_cmd = 'nice make -j' + str(parallelism)
make_test_cmd = 'nice make check -k -j' + str(parallelism)

ignored = ['guality/', 'gfortran.dg/ieee/large_2.f90', 'g++.dg/tls/thread_local-order2.C', 'Testcase exceeded maximum instruction count threshold']

# temporary - hopefully
ignored += ['index0-out.go', 'g++.dg/vect/slp-pr56812.cc', 'gcc.dg/simulate-thread/atomic-other-short.c', 'gcc.dg/sms-1.c', 'gcc.dg/vect/costmodel/ppc/costmodel-pr37194.c',
        'gcc.dg/vect/no-section-anchors-vect-69.c', 'gcc.dg/vect/section-anchors-vect-69.c', 'gcc.dg/vect/slp-perm-9.c', 'gcc.dg/vect/vect-28.c', 'gcc.dg/vect/vect-33-big-array.c',
        'gcc.dg/vect/vect-70.c', 'gcc.dg/vect/vect-87.c', 'gcc.dg/vect/vect-88.c', 'gcc.dg/vect/vect-91.c', 'gcc.dg/vect/vect-93.c',
        'gcc.target/powerpc/bool3-p7.c', 'gcc.target/powerpc/bool3-p8.c', 'gfortran.dg/elemental_subroutine_3.f90', 'gfortran.dg/vect/vect-2.f90',
        'gfortran.dg/vect/vect-3.f90', 'gfortran.dg/vect/vect-4.f90', 'gfortran.dg/vect/vect-5.f90', 'go.test/test/ken/cplx2.go',
        'gcc.dg/ipa/iinline-attr.c', 'gcc.c-torture/execute/pr51581-1.c', 'gcc.c-torture/execute/pr51581-2.c', 'gcc.c-torture/execute/pr53645.c',
        'gcc.dg/vect/pr51581-1.c', 'gcc.dg/vect/pr51581-2.c', 'gcc.dg/vect/pr51581-3.c', 'gcc.dg/vect/pr65947-14.c', 'gcc.dg/vect/pr65947-9.c', 'gcc.dg/pr21643.c',
        'gcc.dg/tree-ssa/phi-opt-11.c', 'gcc.target/powerpc/builtins-1-p9-runnable.c', 'gcc.dg/pr56727-2.c', 'gcc.target/powerpc/loop_align.c', 'gcc.target/powerpc/mmx-packuswb-1.c',
        'gcc.target/powerpc/pr79439.c', 'g++.dg/debug/debug9.C', 'gcc.target/i386/pr59501-3a.c', 'gcc.target/i386/pr70021.c', 'g++.dg/asan/asan_globals_test-wrapper.cc',
        'g++.dg/asan/asan_globals_test.cc', 'g++.dg/asan/asan_oob_test.cc', 'g++.dg/asan/asan_test.cc', 'g++.dg/asan/asan_mem_test.cc', 'gcc.target/powerpc/float128-type-1.c',
        'gcc.target/powerpc/pr82015.c', 'c-c++-common/goacc/kernels-double-reduction-n.c', 'c-c++-common/tsan/race_on_mutex.c', 'gcc.dg/torture/pr52451.c', 'checksyms',
        'c-c++-common/Warray-bounds-4.c', 'g++.dg/lto/pr83121', 'gcc.target/powerpc/builtins-1-le.c', 'gcc.target/powerpc/pr84014.c', 'gcc.target/powerpc/vsx-vector-7.c',
        'g++.dg/tree-ssa/pr19476-1.C', 'g++.dg/tree-ssa/pr19476-1.6', 'g++.dg/pr83239.C', 'g++.dg/lto/20091002-1', 'g++.dg/lto/pr64043', 'g++.dg/lto/pr65193', 'g++.dg/lto/pr65302',
        'g++.dg/lto/pr65316', 'g++.dg/lto/pr65549', 'g++.dg/lto/pr65549', 'g++.dg/lto/pr66180', 'g++.dg/lto/pr66705', 'g++.dg/lto/pr68057', 'g++.dg/lto/pr68057', 'g++.dg/lto/pr68057',
        'g++.dg/lto/pr68057', 'g++.dg/lto/pr69077', 'g++.dg/lto/pr69133', 'g++.dg/lto/pr69137', 'g++.dg/lto/pr79000', 'g++.dg/lto/pr81940', 'g++.dg/lto/pr85176',
        'gcc.dg/strcmpopt_6.c', 'gcc.target/powerpc/builtins-1.c', 'gcc.target/powerpc/p8-vec-xl-xst-v2.c', 'gfortran.dg/lto/pr79108']

def tail(message):
  lines = message.split('\n')
  return '\n'.join(lines[-50:])

class GccTester:
    def __init__(self, revision, options):
        self.original_revision = revision
        self.folder = options.folder
        self.temp = options.temp
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
        self.log('Paralellism: ' + str(parallelism))

    def process_revision(self, revision, configure_cmd):
        self.log('Processing revision: %s' % revision)
        work_folder = self.prepare_revision(revision)
        self.compile_and_test(work_folder, configure_cmd)

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

    def send_email(self, failure = False, failed_tests = 0):
        msg = MIMEMultipart("alternative")

        text = '\n'.join(self.messages)
        text = MIMEText(text, "plain", "utf-8")
        msg.attach(text)

        sender = 'mliska+tester@foxlink.cz'
        recipient = 'mliska@suse.cz'

        subject = '%s: %s : ' % (self.original_revision, 'FAILURE' if failure else 'SUCCESS')
        if not failure:
            subject += 'ALL TEST PASSED' if failed_tests == 0 else '%d TESTS FAILED' % failed_tests

        msg['Subject'] = subject
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
        r = commands.getstatusoutput('git checkout --force ' + revision)
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
        global make_cmd
        if options.fast:
            make_cmd += ' STAGE1_CFLAGS="-O2"'

        r = commands.getstatusoutput(make_cmd)

        if r[0] != 0:
            self.err('Could not build GCC: ' + r[1])

        self.log('Test process has been started')
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
