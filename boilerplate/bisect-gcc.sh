#!/bin/sh

TMPDIR=/dev/shm/gcc-objdir-bisect
LOG=/tmp/gcc.log
SOURCE=~/Programming/gcc2
SOURCEFILE="/home/marxin/Programming/gcc/gcc/testsuite/gfortran.dg/vect/cost-model-pr34445.f"
OPTIONS="-c -misel -O2 -fstack-protector -funroll-all-loops -fno-sched-pressure -fno-tree-ch -fno-tree-forwprop -fno-tree-ter"
GREP="fix_reg_equiv_init"

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
$SOURCE/configure --enable-languages=c,c++,fortran --disable-bootstrap --disable-libsanitizer --without-isl --target=ppc-linux-gnu &>> $LOG || exit 255
nice make -j`nproc` CXXFLAGS="-O0 -fpermissive" CFLAGS="-O0" all-host &>> $LOG || exit 125
date

$TMPDIR/gcc/xg++ -B$TMPDIR/gcc $SOURCEFILE $OPTIONS 2>&1 | grep $GREP

if test $? = 0; then
  echo ICE
  clean
  exit 1
fi

echo OK
clean
exit 0
