#!/bin/bash

source source_medm.sh

#Check provided arguments for record prefix
export P=$1
export R=$2

medm -x -macro "P=$P,R=$R" quadEM.adl &
medm -x -macro "P=$P,R=$R" quadEM_TimeSeriesPlots.adl &
