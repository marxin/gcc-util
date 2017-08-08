#!/bin/sh

TMPDIR=/dev/shm/gcc-objdir
LOG=/tmp/gcc.log
BINDIR=/home/marxin/bin/gcc2

rm -rf $TMPDIR
mkdir $TMPDIR
cd $TMPDIR

~/Programming/gcc2/configure --enable-languages=c,c++ --disable-bootstrap --disable-libsanitizer --target=powerpc-linux-gnu &>> $LOG || exit 255 
make -j9 CXXFLAGS="-O0" CFLAGS="-O0" all-host &>> $LOG || exit 255

$TMPDIR/gcc/xgcc -B$TMPDIR/gcc -O3 -funroll-loops ~/Programming/testcases/pr81747.c 2>&1 | grep 'internal compiler error'

if ! test $? = 0; then
  exit 1
fi

exit 0
