#!/bin/bash

source source_medm.sh

# Check provided arguments for record prefix
if [ -z "$1" ]
then
      # No args provided, default
      export PREFIX="ETC"
else
      # Record prefix provided as argument 1
      export PREFIX=$1
fi

if [[ "$PREFIX" == "ETC" ]]; then
medm -x -noMsg -macro "P=18ID:ETC:,Ti=Ti,Ct=Counter,Bo=Bo,Bi=Bi,Bd=Bd,Li=Li,Lo=Lo" ETC_module.adl &
fi
