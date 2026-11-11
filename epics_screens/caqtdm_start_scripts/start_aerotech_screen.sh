#!/bin/bash

source source_caqtdm.sh

# Check provided arguments for record prefix
if [ -z "$1" ]
then
      # No args provided, default
      export PREFIX="18ID_Aerotech_C:"
else
      # Record prefix provided as argument 1
      export PREFIX=$1
fi

caQtDM -attach -noMsg -macro "P=${PREFIX}, M=m1," Automation1AxisStatus.ui &
#caQtDM -attach -noMsg -macro "P=${PREFIX}, M=m1, R=pm1:," Automation1PSO.ui &
