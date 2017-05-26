#!/bin/sh

TMPDIR=`mktemp --directory`
LOG=/tmp/gcc.log
BINDIR=/home/marxin/bin/gcc2
cd $TMPDIR

function clean {
  rm -rf $TMPDIR &>> $LOG
}

function quit {
  clean
  exit 255
}  

~/Programming/gcc2/configure --enable-languages=c,c++ --prefix=$BINDIR --disable-bootstrap --disable-libsanitizer &>> $LOG || quit
make -j9 &>> $LOG || quit
make install &>> $LOG || quit

cd /home/marxin/Programming/icu/icu4c/source && cd i18n && $BINDIR/bin/g++ -D_REENTRANT -DU_HAVE_ELF_H=1 -DU_HAVE_ATOMIC=1 -DU_HAVE_STRTOD_L=1 -I. -I../common -DU_ATTRIBUTE_DEPRECATED= -DU_I18N_IMPLEMENTATION -O2 -m32 -W -Wall -pedantic -Wpointer-arith -Wwrite-strings -Wno-long-long -std=c++11 -c -DPIC -fPIC -o precision.o precision.cpp && cd .. && make && cd  /home/marxin/Programming/icu/icu4c/source/test/cintltst && LD_LIBRARY_PATH=../../lib:../../stubdata:../../tools/ctestfw:$LD_LIBRARY_PATH ./cintltst /tsformat/crelativedateformattest &>> $LOG

if ! test $? = 0; then
  clean
  exit 1
fi

clean
exit 0
