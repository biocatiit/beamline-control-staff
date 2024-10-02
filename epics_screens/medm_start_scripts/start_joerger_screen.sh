#!/bin/bash

source source_medm.sh

medm -x -macro "P=18ID:, S=scaler2" scaler16_full.adl &
