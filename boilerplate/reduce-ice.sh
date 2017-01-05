#!/bin/sh

TC1=${1:-tc.i}
COMMAND="gcc -O2 -c $TC1"

$COMMAND 2>&1 | grep 'internal compiler error'

if ! test $? = 0; then
  exit 1
fi

$COMMAND $TC1 2>/dev/null

if ! test $? = 0; then
  exit 1
fi

exit 0
