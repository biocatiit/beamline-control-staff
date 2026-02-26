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

caQtDM -attach -noMsg -macro "P=18ID:Scans:, S=scan$VAL" scan_full.ui &
