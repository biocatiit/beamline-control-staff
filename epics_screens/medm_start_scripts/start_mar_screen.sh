#!/bin/bash

source source_medm.sh

medm -x -macro "P=Mar165:, R=cam1:" marCCD.adl &
