#!/bin/bash

source source_caqtdm.sh

#Check provided arguments for record prefix
if [ -z "$1" ]
then
      # No args provided, default
      export CAMERACHOICE=inline
else
      # Record prefix provided as argument 1
      export CAMERACHOICE=$1
fi

if [[ "$CAMERACHOICE" == "tripod" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:D:Tripod:, R=cam1:, C=FLIR-BFS-PGE-23S6C" ADSpinnaker.ui &
elif [[ "$CAMERACHOICE" == "inline" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:D:Inline:, R=cam1:, C=FLIR-BFS-PGE-23S6C" ADSpinnaker.ui &
elif [[ "$CAMERACHOICE" == "screen" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:C:Screen:, R=cam1:, C=FLIR-BFS-PGE-23S6M" ADSpinnaker.ui &
elif [[ "$CAMERACHOICE" == "mono1" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:C:Mono1:, R=cam1:, C=FLIR-BFS-PGE-23S6M" ADSpinnaker.ui &
elif [[ "$CAMERACHOICE" == "mono2" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:C:Mono2:, R=cam1:, C=FLIR-BFS-PGE-23S6M" ADSpinnaker.ui &
elif [[ "$CAMERACHOICE" == "coflow_perp" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:D:CoflowPerp:, R=cam1:, C=FLIR-BFS-PGE-23S6C" ADSpinnaker.ui &
elif [[ "$CAMERACHOICE" == "coflow_needle" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:D:CoflowNeedle:, R=cam1:, C=PGR_Blackfly_23S6C" ADSpinnaker.ui &
fi
