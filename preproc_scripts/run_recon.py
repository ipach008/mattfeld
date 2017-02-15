#!/usr/bin/env python

#BSUB -o /scratch/madlab/surfaces/run_recon_out
#BSUB -e /scratch/madlab/surfaces/run_recon_err

import os
from glob import glob

from nipype import Node, Function, Workflow, IdentityInterface
from nipype.interfaces.freesurfer import ReconAll
from nipype.interfaces.io import DataGrabber

# CURRENT PROJECT DATA DIRECTORY
data_dir = '/scratch/PSB6351_2017/ds008_R2.0.0'

# CURRENT PROJECT SUBJECT IDS
sids = ['sub-01', 'sub-02', 'sub-03', 'sub-04', 'sub-05',
        'sub-06', 'sub-07', 'sub-08', 'sub-09', 'sub-10',
        'sub-11', 'sub-12', 'sub-13', 'sub-14', 'sub-15']

info = dict(T1=[['subject_id']])

infosource = Node(IdentityInterface(fields=['subject_id']), name='infosource')
infosource.iterables = ('subject_id', sids)

# Create a datasource node to get the T1 file
datasource = Node(DataGrabber(infields=['subject_id'],outfields=info.keys()),name = 'datasource')
datasource.inputs.template = '%s/%s'
datasource.inputs.base_directory = os.path.abspath(data_dir)
datasource.inputs.field_template = dict(T1='%s/anat/*_T1w.nii.gz')
datasource.inputs.template_args = info
datasource.inputs.sort_filelist = True

reconall_node = Node(ReconAll(), name='reconall_node')
reconall_node.inputs.openmp = 2
reconall_node.inputs.subjects_dir = os.environ['SUBJECTS_DIR']
reconall_node.inputs.terminal_output = 'allatonce'
reconall_node.plugin_args={'bsub_args': ('-q PQ_madlab -n 2'), 'overwrite': True}

wf = Workflow(name='fsrecon')

wf.connect(infosource, 'subject_id', datasource, 'subject_id')
wf.connect(infosource, 'subject_id', reconall_node, 'subject_id')
wf.connect(datasource, 'T1', reconall_node, 'T1_files')

wf.base_dir = os.path.abspath('/scratch/PSB63517_2017/crash/mattfeld/week6/')
#wf.config['execution']['job_finished_timeout'] = 65

wf.run(plugin='LSF', plugin_args={'bsub_args': ('-q PQ_madlab')})
