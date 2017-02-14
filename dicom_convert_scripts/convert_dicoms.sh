#!/bin/bash

#BSUB -J psb6351_dcm_convert
#BSUB -o /scratch/PSB6351_2017/crash/mattfeld/dcm_convert_out
#BSUB -e /scratch/PSB6351_2017/crash/mattfeld/dcm_convert_err

./dicomconvert2_GE.py -d /scratch/PSB6351_2017/dicoms -o /scratch/PSB6351_2017/week4/mattfeld/data4 -f heuristic.py -q PQ_madlab -c dcm2nii -s subj001

