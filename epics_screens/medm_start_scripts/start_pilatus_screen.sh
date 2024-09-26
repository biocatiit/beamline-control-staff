#!/bin/bash

source source_medm.sh

Check provided arguments for record prefix
if [ -z "$1" ]
then
      # No args provided, default
      export PREFIX="2"
else
      # Record prefix provided as argument 1
      export PREFIX=$1
fi

# R = Record name for digital IO not including byte/word, and bit number
# Digital IO naming
# $(DMC)$(R)<Byte or word num><Type Bo or Bi><Bit>

medm -x -noMsg -macro "P=18IDpil1M:, R=cam1:" pilatusDetector.adl &

