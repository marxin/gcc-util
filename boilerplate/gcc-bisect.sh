#!/bin/sh

TMPDIR=/dev/shm/gcc-objdir
LOG=/tmp/gcc.log
BINDIR=/home/marxin/bin/gcc2

rm -rf $TMPDIR
mkdir $TMPDIR
cd $TMPDIR

~/Programming/gcc2/configure --enable-languages=c,c++ --disable-bootstrap --disable-libsanitizer --target=s390x-linux-gnu &>> $LOG || exit 255 
make -j9 CXXFLAGS="-O0 -fpermissive" CFLAGS="-O0" all-host &>> $LOG || exit 125

$TMPDIR/gcc/xg++ -B$TMPDIR/gcc /home/marxin/Programming/gcc/gcc/testsuite/g++.dg/abi/nvptx-nrv1.C -fno-early-inlining -Os  2>&1 | grep 'internal compiler error'

if test $? = 0; then
  exit 1
fi

exit 0
