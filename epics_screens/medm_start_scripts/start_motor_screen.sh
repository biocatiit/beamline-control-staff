#!/bin/bash

source source_medm.sh

medm -x -macro "P=$1, M=$2:" motorx.adl &
