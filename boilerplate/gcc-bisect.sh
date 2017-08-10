#!/bin/sh

TMPDIR=/dev/shm/gcc-objdir
LOG=/tmp/gcc.log
SOURCE=~/Programming/gcc2

function clean {
  cd $SOURCE
  git checkout --force
}

# apply patch
clean
patch -p1 < /tmp/p

rm -rf $TMPDIR
mkdir $TMPDIR
cd $TMPDIR

date
$SOURCE/configure --enable-languages=c,c++ --disable-bootstrap --disable-libsanitizer --target=m32c-rtems &>> $LOG || exit 255 
make -j9 CXXFLAGS="-O0 -fpermissive" CFLAGS="-O0" all-host &>> $LOG || exit 125
date

$TMPDIR/gcc/xgcc -B$TMPDIR/gcc /tmp/main.c ~/Programming/testcases/pr64546.c -mcpu=m32cm -Os -c 2>&1 | grep 'internal compiler error'

if test $? = 0; then
  echo ICE
  clean
  exit 1
fi

echo OK
clean
exit 0
