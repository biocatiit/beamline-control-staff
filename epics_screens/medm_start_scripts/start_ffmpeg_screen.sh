#!/bin/bash

source source_medm.sh

medm -x -macro "P=18ID:FLIR:D:Tripod:, R=ffmstream1:" ffmpegStream.adl &
