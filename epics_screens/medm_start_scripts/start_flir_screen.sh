#!/bin/bash

source source_medm.sh

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
medm -x -macro "P=18ID:FLIR:D:Tripod:, R=cam1:, C=FLIR-BFS-PGE-23S6C" ADSpinnaker.adl &
elif [[ "$CAMERACHOICE" == "inline" ]]; then
medm -x -macro "P=18ID:FLIR:D:Inline:, R=cam1:, C=FLIR-BFS-PGE-23S6C" ADSpinnaker.adl &
elif [[ "$CAMERACHOICE" == "screen" ]]; then
medm -x -macro "P=18ID:FLIR:C:Screen:, R=cam1:, C=FLIR-BFS-PGE-23S6M" ADSpinnaker.adl &
elif [[ "$CAMERACHOICE" == "mono1" ]]; then
medm -x -macro "P=18ID:FLIR:C:Mono1:, R=cam1:, C=FLIR-BFS-PGE-23S6M" ADSpinnaker.adl &
elif [[ "$CAMERACHOICE" == "mono2" ]]; then
medm -x -macro "P=18ID:FLIR:C:Mono2:, R=cam1:, C=FLIR-BFS-PGE-23S6M" ADSpinnaker.adl &
fi
