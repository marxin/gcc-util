#!/bin/sh

TMPDIR=/dev/shm/gcc-objdir-bisect
LOG=/tmp/gcc.log
SOURCE=~/Programming/gcc2
SOURCEFILE="/home/marxin/Programming/gcc2/gcc/testsuite/gcc.dg/pr94292.c"
OPTIONS="-c -O -g -fno-tree-dce"
GREP="internal compiler"

TARGET="arm-linux-gnueabi"
#TARGET="aarch64-linux-gnu"
#TARGET="ppc64le-linux-gnu"
#TARGET="ppc64-linux-gnu"
#TARGET="s390x-linux-gnu"

function clean {
  cd $SOURCE
  git checkout --force
}

# apply patch
clean
DATE=`git show -s --format=%ci`

rm -rf $TMPDIR
mkdir $TMPDIR
cd $TMPDIR

echo "Starting: " `date`
echo "Revision date: $DATE"
$SOURCE/configure --enable-languages=c,c++,fortran --disable-bootstrap --disable-libsanitizer --target=$TARGET &>> $LOG || exit 255
nice make -j`nproc` CXXFLAGS="-O0 -fpermissive" CFLAGS="-O0" all-host &>> $LOG || exit 125
echo "Done: " `date`

$TMPDIR/gcc/xgcc -B$TMPDIR/gcc $SOURCEFILE $OPTIONS 2>&1 | grep "$GREP"

if test $? = 0; then
  echo ICE
  clean
  exit 1
fi

echo OK
clean
exit 0
