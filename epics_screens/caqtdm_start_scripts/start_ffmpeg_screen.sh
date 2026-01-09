#!/bin/bash

source source_caqtdm.sh

if [ -z "$1" ]
then
      # No args provided, default
      export CAMERACHOICE=inline
else
      # Record prefix provided as argument 1
      export CAMERACHOICE=$1
fi

if [[ "$CAMERACHOICE" == "tripod" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:D:Tripod:, R=ffmstream1:" ffmpegStream.ui &
elif [[ "$CAMERACHOICE" == "inline" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:D:Inline:, R=ffmstream1:" ffmpegStream.ui &
elif [[ "$CAMERACHOICE" == "screen" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:C:Screen:, R=ffmstream1:" ffmpegStream.ui &
elif [[ "$CAMERACHOICE" == "mono1" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:C:Mono1:, R=ffmstream1:" ffmpegStream.ui &
elif [[ "$CAMERACHOICE" == "mono2" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:C:Mono2:, R=ffmstream1:" ffmpegStream.ui &
elif [[ "$CAMERACHOICE" == "coflow_perp" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:D:CoflowPerp:, R=ffmstream1:" ffmpegStream.ui &
elif [[ "$CAMERACHOICE" == "coflow_needle" ]]; then
      caQtDM -attach -noMsg -macro "P=18ID:FLIR:D:CoflowNeedle:, R=ffmstream1:" ffmpegStream.ui &
fi
