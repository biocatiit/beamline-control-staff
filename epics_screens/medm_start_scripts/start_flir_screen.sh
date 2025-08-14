#!/bin/bash

source source_medm.sh

medm -x -macro "P=18ID:FLIR:D:Tripod:, R=cam1:, C=FLIR-BFS-PGE-23S6C" ADSpinnaker.adl &
