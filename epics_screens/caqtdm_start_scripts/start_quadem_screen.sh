#!/bin/bash

source source_caqtdm.sh

#Check provided arguments for record prefix
export P=$1
export R=$2

caQtDM -attach -noMsg -macro "P=$P,R=$R" quadEM.ui &
# caQtDM -attach -noMsg -macro "P=$P,R=$R" quadEM_TimeSeriesPlots.ui &
