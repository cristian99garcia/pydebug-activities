#!/bin/sh
echo comand line:"$@"
CURDIR=`cd $(dirname $0)/..; pwd`
echo current directory is $CURDIR
export HOME=$SUGAR_ACTIVITY_ROOT/data
#export PYTHONPATH=$CURDIR:$CURDIR/lib/python2.6/site-packages:$PYTHONPATH
#export PATH=$CURDIR/bin:$PATH
#export SUGAR_BUNDLE_PATH=$CURDIR
#export IPYTHONDIR=$CURDIR
#export LD_LIBRARY_PATH=$CURDIR/lib:$LD_LIBRARY_PATH
#export SUGAR_SCALING=XO
exec sugar-activity pydebug.PyDebugActivity -s "$@"
