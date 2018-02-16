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

rm -rf $TMPDIR
mkdir $TMPDIR
cd $TMPDIR

date
$SOURCE/configure --enable-languages=c,c++ --disable-bootstrap --disable-libsanitizer --target=ppc64le-linux-gnu  &>> $LOG || exit 255 
nice make -j9 CXXFLAGS="-O0 -fpermissive" CFLAGS="-O0" all-host &>> $LOG || exit 125
date

$TMPDIR/gcc/xg++ -B$TMPDIR/gcc /tmp/ice.c  --param ira-max-conflict-table-size=0 -O3 2>&1 | grep 'internal compiler error'

if test $? = 0; then
  echo ICE
  clean
  exit 0
fi

echo OK
clean
exit 1
