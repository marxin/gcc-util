#!/bin/sh

TMPDIR=`mktemp --directory`
LOG=/tmp/gcc.log
BINDIR=/home/marxin/bin/gcc3
cd $TMPDIR

function clean {
  rm -rf $TMPDIR &>> $LOG
}

function quit {
  clean
  exit 255
}  

~/Programming/gcc/configure --enable-languages=c --prefix=$BINDIR --disable-bootstrap --disable-libsanitizer &>> $LOG || quit
make -j9 &>> $LOG || quit
make install &>> $LOG || quit

$BINDIR/bin/gcc ~/Programming/testcases/tc.c -m32 -O -o /tmp/a.out && /tmp/a.out

if ! test $? = 0; then
  exit 1
fi

exit 0
