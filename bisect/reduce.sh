#!/bin/bash
TESTCASE=${1:-testcase.i}

gcc -c -O2 -w $TESTCASE 2>&1 | grep -q ' internal compiler error: Segmentation fault'
if ! test $? = 0; then
exit 1
fi
exit 0
