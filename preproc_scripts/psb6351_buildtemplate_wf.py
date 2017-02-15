#!/usr/bin/env python

import os
from nipype.pipeline.engine import Workflow
from nipype.pipeline.engine import Node
from nipype.pipeline.engine import MapNode
from nipype.pipeline.engine import JoinNode
from nipype.interfaces.utility import IdentityInterface
from nipype.interfaces.utility import Function
from nipype.interfaces import fsl
from nipype.interfaces import ants
from glob import glob
from nipype.interfaces.io import DataSink
from nipype.interfaces.ants.legacy import buildtemplateparallel
#from utility_scripts.fs_skullstrip_util import create_freesurfer_skullstrip_workflow
import sys
sys.path.append("/scratch/PSB6351_2017/utility_scripts")
from fs_skullstrip_util import create_freesurfer_skullstrip_workflow

fs_projdir = '/scratch/PSB6351_2017/ds008_R2.0.0/surfaces'
projdir = '/scratch/PSB6351_2017/ds008_R2.0.0'
workdir = '/scratch/PSB6351_2017/crash/mattfeld/bld_template'
workingdir = os.path.join(workdir,'ants_template') #working directory
if not os.path.exists(workingdir):
    os.makedirs(workingdir)

fs_skullstrip_wf = create_freesurfer_skullstrip_workflow()
fs_skullstrip_wf.inputs.inputspec.subjects_dir = fs_projdir

sids = ['sub-01', 'sub-02', 'sub-03', 'sub-04', 'sub-05',
        'sub-06', 'sub-07', 'sub-09', 'sub-10',
        'sub-11', 'sub-12', 'sub-13', 'sub-14', 'sub-15']

# Set up the FreeSurfer skull stripper work flow
ants_buildtemplate_wf = Workflow(name='ants_buildtemplate_wf')
ants_buildtemplate_wf.base_dir = workingdir

subjID_infosource = Node(IdentityInterface(fields=['subject_id','subjects_dir']), name = 'subjID_infosource')
#subjID_infosource.inputs.subject_ids = sids
subjID_infosource.iterables = ('subject_id', sids)

ants_buildtemplate_wf.connect(subjID_infosource, 'subject_id', fs_skullstrip_wf, 'inputspec.subject_id')

# Use a JoinNode to aggregrate all of the outputs from the fs_skullstrip_wf
skullstripped_images = JoinNode(IdentityInterface(fields=['brainonly_images']),
                             joinsource='subjID_infosource',
                             joinfield='brainonly_images', name='skullstripped_images')
ants_buildtemplate_wf.connect(fs_skullstrip_wf, 'outputspec.skullstripped_file', skullstripped_images, 'brainonly_images')

# Create a FLIRT node to rigid body transform (6 DOF) skullstripped brains to a MNI template
firstpass_flirt = MapNode(fsl.FLIRT(),
                          iterfield=['in_file'],
                          name='firstpass_flirt')
firstpass_flirt.inputs.reference = "/scratch/PSB6351_2017/ds008_R2.0.0/template/MNI/OASIS-30_Atropos_template_in_MNI152.nii.gz"
firstpass_flirt.inputs.dof = 6
ants_buildtemplate_wf.connect(skullstripped_images, 'brainonly_images', firstpass_flirt, 'in_file')

ants_template = Node(buildtemplateparallel(), name = 'ants_template')
ants_template.inputs.parallelization = 0
ants_template.inputs.bias_field_correction = True
ants_template.inputs.gradient_step_size = 0.2
ants_template.inputs.max_iterations = [100, 70, 50, 20]
ants_template.inputs.rigid_body_registration = True
ants_template.inputs.similarity_metric = 'CC'
ants_buildtemplate_wf.connect(firstpass_flirt, 'out_file', ants_template, 'in_files')

# Move the results to a designated results folder
datasink = Node(DataSink(), name="datasink")
datasink.inputs.base_directory = os.path.join(projdir)
ants_buildtemplate_wf.connect(ants_template, 'final_template_file', datasink, 'template.StudyTemplate')

# Run the workflow
ants_buildtemplate_wf.run(plugin='LSF', plugin_args={'bsub_args' : ('-q PQ_madlab')})

