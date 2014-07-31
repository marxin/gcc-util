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

targets = 'aarch64-elf aarch64-linux-gnu \
  alpha-linux-gnu alpha-freebsd6 alpha-netbsd alpha-openbsd \
  alpha64-dec-vms alpha-dec-vms am33_2.0-linux \
  arc-elf32OPT-with-cpu=arc600 arc-elf32OPT-with-cpu=arc700 \
  arc-linux-uclibcOPT-with-cpu=arc700 arceb-linux-uclibcOPT-with-cpu=arc700 \
  arm-wrs-vxworks arm-netbsdelf \
  arm-linux-androideabi arm-uclinux_eabi arm-eabi \
  arm-symbianelf avr-rtems avr-elf \
  bfin-elf bfin-uclinux bfin-linux-uclibc bfin-rtems bfin-openbsd \
  c6x-elf c6x-uclinux cr16-elf cris-elf cris-linux crisv32-elf crisv32-linux \
  epiphany-elf epiphany-elfOPT-with-stack-offset=16 fido-elf \
  fr30-elf frv-elf frv-linux h8300-elf h8300-rtems hppa-linux-gnu \
  hppa-linux-gnuOPT-enable-sjlj-exceptions=yes hppa64-linux-gnu \
  hppa2.0-hpux10.1 hppa64-hpux11.3 \
  hppa64-hpux11.0OPT-enable-sjlj-exceptions=yes hppa2.0-hpux11.9 \
  i686-pc-linux-gnu i686-apple-darwin i686-apple-darwin9 i686-apple-darwin10 \
  i486-freebsd4 i686-freebsd6 i686-kfreebsd-gnu \
  i686-netbsdelf9 i686-knetbsd-gnu i686-openbsd i686-openbsd3.0 \
  i686-elf i686-kopensolaris-gnu i686-symbolics-gnu i686-pc-msdosdjgpp \
  i686-lynxos i686-nto-qnx \
  i686-rtems i686-solaris2.10 i686-wrs-vxworks \
  i686-wrs-vxworksae \
  i686-cygwinOPT-enable-threads=yes i686-mingw32crt ia64-elf \
  ia64-freebsd6 ia64-linux ia64-hpux ia64-hp-vms iq2000-elf lm32-elf \
  lm32-rtems lm32-uclinux m32c-rtems m32c-elf m32r-elf m32rle-elf m32r-rtems \
  m32r-linux m32rle-linux m68k-elf m68k-netbsdelf \
  m68k-openbsd m68k-uclinux m68k-linux m68k-rtems \
  mcore-elf mep-elf microblaze-linux microblaze-elf \
  mips-netbsd \
  mips64el-st-linux-gnu mips64octeon-linux mipsisa64r2-linux \
  mipsisa32r2-linux-gnu mipsisa64r2-sde-elf mipsisa32-elfoabi \
  mipsisa64-elfoabi mipsisa64r2el-elf mipsisa64sr71k-elf mipsisa64sb1-elf \
  mipsel-elf mips64-elf mips64vr-elf mips64orion-elf mips-rtems \
  mips-wrs-vxworks mipstx39-elf mmix-knuth-mmixware mn10300-elf moxie-elf \
  moxie-uclinux moxie-rtems \
  msp430-elf \
  nds32le-elf nds32be-elf \
  nios2-elf nios2-linux-gnu \
  pdp11-aout picochip-elfOPT-enable-obsolete \
  powerpc-darwin8 \
  powerpc-darwin7 powerpc64-darwin powerpc-freebsd6 powerpc-netbsd \
  powerpc-eabispe powerpc-eabisimaltivec powerpc-eabisim ppc-elf \
  powerpc-eabialtivec powerpc-xilinx-eabi powerpc-eabi \
  powerpc-rtems4.11OPT-enable-threads=yes powerpc-linux_spe \
  powerpc-linux_paired powerpc64-linux_altivec \
  powerpc-wrs-vxworks powerpc-wrs-vxworksae powerpc-lynxos powerpcle-elf \
  powerpcle-eabisim powerpcle-eabi rs6000-ibm-aix4.3 rs6000-ibm-aix5.1.0 \
  rs6000-ibm-aix5.2.0 rs6000-ibm-aix5.3.0 rs6000-ibm-aix6.0 \
  rl78-elf rx-elf s390-linux-gnu s390x-linux-gnu s390x-ibm-tpf sh-elf \
  shle-linux sh-netbsdelf sh-superh-elf sh5el-netbsd sh64-netbsd sh64-linux \
  sh64-elfOPT-with-newlib sh-rtems sh-wrs-vxworks sparc-elf \
  sparc-leon-elf sparc-rtems sparc-linux-gnu \
  sparc-leon3-linux-gnuOPT-enable-target=all sparc-netbsdelf \
  sparc64-sun-solaris2.10OPT-with-gnu-ldOPT-with-gnu-asOPT-enable-threads=posix \
  sparc-wrs-vxworks sparc64-elf sparc64-rtems sparc64-linux sparc64-freebsd6 \
  sparc64-netbsd sparc64-openbsd spu-elf \
  tilegx-linux-gnu tilegxbe-linux-gnu tilepro-linux-gnu \
  v850e-elf v850-elf vax-linux-gnu \
  vax-netbsdelf vax-openbsd x86_64-apple-darwin \
  x86_64-pc-linux-gnuOPT-with-fpmath=avx \
  x86_64-elfOPT-with-fpmath=sse x86_64-freebsd6 x86_64-netbsd \
  x86_64-knetbsd-gnu x86_64-w64-mingw32 \
  x86_64-mingw32OPT-enable-sjlj-exceptions=yes xstormy16-elf xtensa-elf \
  xtensa-linux i686-interix3OPT-enable-obsolete score-elfOPT-enable-obsolete'

all_targets = [x for x in targets.split(' ') if x]
parallelism = multiprocessing.cpu_count()
make_cmd = 'make -k -j' + str(parallelism)

def err(message):
  log(message)
  exit(1)

def log(message):
  d = str(datetime.datetime.now())
  print('[%s]: %s' % (d, message))

frontends = { 'c': 'cc1', 'c++': 'cc1plus', 'go': 'go1', 'fortran': 'f951', 'ada': 'gnat1', 'go': 'go1', 'java': 'jc1', 'objc': 'cc1obj', 'obj-c++': 'cc1plusobj'  }

parser = OptionParser()
parser.add_option("-f", "--folder", dest="folder", help="git repository folder")
parser.add_option("-d", "--destination", dest="destination", help = "destination folder")
parser.add_option("-l", "--languages", dest="languages", help = "languages")
parser.add_option("-c", "--checking", action="store_true", dest="checking", default=False, help = "enable checking")
parser.add_option("-s", "--subset", action="store_true", dest="subset", default=False, help = "subset of targets")
parser.add_option("-t", "--targets", dest="targets", default = ','.join(all_targets), help = "targets")

(options,args) = parser.parse_args()

if not options.folder:
  parser.error('folder not specified')

if not options.destination:
  parser.error('destination')

if not os.path.exists(options.destination):
  os.mkdir(options.destination)

if options.languages.find('all') != -1:
  options.languages = options.languages.replace('all', ','.join(frontends.keys()))

options.targets = options.targets.split(',')

if options.subset:
  subset = map(lambda x: x.split('-')[0], options.targets)
  prefixes = (set(subset))
  options.targets= map(lambda x: filter(lambda y: y.startswith(x), options.targets)[0], prefixes)

# build of configure command line
configure_options = '--disable-bootstrap'

if not options.checking:
  configure_options = configure_options + ' --enable-checking=release'

if options.languages != None:
  configure_options = configure_options + ' --enable-languages=' + options.languages

log('Built configure options: ' + configure_options)

failures = []
targets = options.targets
# targets = filter(lambda x: x.startswith('rs6000'), options.targets)

for (i, v) in enumerate(targets):
  log('configure: %s [%u/%u]' % (v, i + 1, len(targets)))
  tokens = v.split('OPT')
  target = tokens[0]

  folder = os.path.join(options.destination, v)

  if not os.path.exists(folder):
    os.mkdir(folder)

  os.chdir(folder)

  configure_location = os.path.join(options.folder, 'configure')
  r = commands.getstatusoutput(configure_location + ' ' + configure_options + ' --target=' + target + ' ' + ' '.join(tokens[1:]))

  if r[0] != 0:
    err('Configuration failed: %s' % (r[1]))

  log('building: %s [%u/%u]' % (v, i + 1, len(targets)))

  r = commands.getstatusoutput(make_cmd)
  log('Make exited with: %u' % r[0])

  matches = filter(lambda x: not x[1], map(lambda x: (x, os.path.exists(os.path.join('gcc', x))), options.languages))
  missing_fe = ' '.join(map(lambda x: x[0]))

  if any(matches):
    failures.append(v)

  if not os.path.exists('../logs'):
    os.mkdir('../logs')

  with open(os.path.join('../logs', v + '.log'), "w") as text_file:
    text_file.write(r[1])

  if not any(matches):
    shutil.rmtree(folder)

log('Wrong configurations: ' + str(failures))
