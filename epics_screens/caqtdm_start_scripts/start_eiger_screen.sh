#!/bin/bash

source source_caqtdm.sh

caQtDM -attach -noMsg -macro "P=18ID:EIG2:, R=cam1:" eiger2Detector.ui &
