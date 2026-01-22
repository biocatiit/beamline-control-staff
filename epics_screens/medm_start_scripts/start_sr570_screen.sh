#!/bin/bash

source source_caqtdm.sh

Check provided arguments for record prefix
if [ -z "$1" ]
then
      # No args provided, default
      export VAL=1
else
      # Record prefix provided as argument 1
      export VAL=$1
fi

medm -x -noMsg -macro "P=18ID:SR570:$VAL:, A=asyn_$VAL" SR570.ui &
