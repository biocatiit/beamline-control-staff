#!/bin/bash

source source_medm.sh

medm -x -macro "P=18ID:EIG2:, R=cam1:" eiger2Detector.adl &
