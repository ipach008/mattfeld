#! /bin/bash

#BSUB -J madlab_recon_edits
#BSUB -o run_recon_afteredits_out
#BSUB -e run_recon_afteredits_err

for subj in 'sub-09'; do

# re-running it after control points have been made or (if both control points & pial edits have been made)
#cmd="recon-all -subjid ${subj} -autorecon2-cp -autorecon3 -no-isrunning"

# re-running it after pial edits have been made
cmd="recon-all -subjid ${subj} -autorecon-pial -autorecon3 -no-isrunning"

# re-running it after wm edits have been made
#cmd="recon-all -subjid ${subj} -autorecon2-wm -autorecon3 -no-isrunning"

echo `echo ${cmd}` | bsub -q PQ_madlab -e /scratch/PSB6351_2017/week6/mattfeld/recon_afteredits_${subj}_err -o /scratch/PSB6351_2017/week6/mattfeld/recon_afteredits_${subj}_out

done
