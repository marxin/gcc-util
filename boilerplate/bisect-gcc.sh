#!/bin/sh

TMPDIR=/dev/shm/gcc-objdir-bisect
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
$SOURCE/configure --enable-languages=c,c++ --disable-bootstrap --disable-libsanitizer --target=arm-linux-gnueabi --without-isl --with-as=/usr/bin/arm-suse-linux-gnueabi-as &>> $LOG || exit 255
nice make -j9 CXXFLAGS="-O0 -fpermissive" CFLAGS="-O0" all-host &>> $LOG || exit 125
date

$TMPDIR/gcc/xg++ -B$TMPDIR/gcc -Ofast /tmp/ice.ii 2>&1 | grep 'gimplify_expr'

if test $? = 0; then
  echo ICE
  clean
  exit 1
fi

echo OK
clean
exit 0
