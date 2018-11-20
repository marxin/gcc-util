#!/bin/sh

TMPDIR=/dev/shm/gcc-objdir-bisect
LOG=/tmp/gcc.log
SOURCE=~/Programming/gcc

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
$SOURCE/configure --enable-languages=c,c++ --disable-bootstrap --disable-libsanitizer --target=aarch64-linux-gnu --without-isl  &>> $LOG || exit 255
nice make -j9 CXXFLAGS="-O0 -fpermissive" CFLAGS="-O0" all-host &>> $LOG || exit 125
date

$TMPDIR/gcc/xg++ -B$TMPDIR/gcc -O2 /tmp/Unified.ii  2>&1 | grep 'contains_placeholder_p'

if test $? = 0; then
  echo ICE
  clean
  exit 0
fi

echo OK
clean
exit 1
