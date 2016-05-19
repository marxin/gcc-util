#!/bin/sh

TC1=${1:-tc.i}

g++ $TC1 >&1 | grep 'internal compiler error'

if ! test $? = 0; then
  exit 1
fi

exit 0
