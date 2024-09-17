#!/bin/bash

source source_medm.sh

medm -x -macro "P=18ID:mcs:, M=mca" SIS38XX.adl &
