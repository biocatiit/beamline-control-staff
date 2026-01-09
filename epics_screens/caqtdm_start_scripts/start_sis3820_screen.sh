#!/bin/bash

source source_caqtdm.sh

caQtDM -attach -noMsg -macro "P=18ID:mcs:, M=mca" SIS38XX.ui &
