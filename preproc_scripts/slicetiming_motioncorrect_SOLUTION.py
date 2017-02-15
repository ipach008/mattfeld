#!/usr/bin/env python

import os
import nipype.interfaces.fsl as fsl
import nipype.interfaces.nipy as nipy
import nipype.interfaces.freesurfer as fs
import nipype.interfaces.io as nio
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util  
import nipype.interfaces.afni as afni

def pickfirst(func):
    if isinstance(func, list):
        return func[0]
    else:
        return func

def pickvol(filenames, fileidx, which):
    from nibabel import load
    import numpy as np
    if which.lower() == 'first':
        idx = 0
    elif which.lower() == 'middle':
        idx = int(np.ceil(load(filenames[fileidx]).get_shape()[3]/2))
    else:
        raise Exception('unknown value for volume selection : %s'%which)
    return idx

def get_subs(subject_id, mri_files):
    subs = []
    subs.append(('_subject_id_%s/' %subject_id, ''))
    for i, mri_file in enumerate(mri_files):
        subs.append(('_motion_sltime_correct%d/' %i, ''))
        subs.append(('_motion_correct%d/' %i, ''))
    return subs

def calc_slicetimes(filenames, TR):
    from nibabel import load
    import numpy as np
    all_sliceTimes = []
    for file in filenames:
       n_slices = load(file).get_shape()[2]
       slice_order = range(0,n_slices,2)+range(1,n_slices,2)
       slice_order = np.argsort(slice_order)
       sliceTimes = (slice_order * TR/n_slices).tolist()
       all_sliceTimes.append(sliceTimes)

    return all_sliceTimes

proj_dir = '/scratch/PSB6351_2017/ds008_R2.0.0'
work_dir = '/scratch/PSB6351_2017/crash/mattfeld/week5_fsl'
sink_dir = '/scratch/PSB6351_2017/week5/mattfeld/data_fsl'

slice_timer = 'FSL'

#sids = ['sub-01']
sids = ['sub-01', 'sub-02', 'sub-03', 'sub-04', 'sub-05',
        'sub-06', 'sub-07', 'sub-08', 'sub-09', 'sub-10',
        'sub-11', 'sub-12', 'sub-13', 'sub-14', 'sub-15']

# Workflow
motcor_sltimes_wf = pe.Workflow("motcor_sltimes_wf")
motcor_sltimes_wf.base_dir = work_dir

# Define the outputs for the workflow
output_fields = ['reference',
                 'motion_parameters',
                 'motion_corrected_files'
                 'motion_sltime_corrected_files',
                 'motion_plots']
outputspec = pe.Node(util.IdentityInterface(fields=output_fields),
                     name='outputspec')


# Node: subject_iterable
subj_iterable = pe.Node(util.IdentityInterface(fields=['subject_id'],
                                               mandatory_inputs=True),
                        name='subj_interable')
subj_iterable.iterables = ('subject_id', sids)

info = dict(mri_files=[['subject_id']])

# Create a datasource node to get the mri files
datasource = pe.Node(nio.DataGrabber(infields=['subject_id'], outfields=info.keys()), name='datasource')
datasource.inputs.template = '*'
datasource.inputs.base_directory = os.path.abspath(proj_dir)
datasource.inputs.field_template = dict(mri_files='%s/func/*_bold.nii.gz')
datasource.inputs.template_args = info
datasource.inputs.sort_filelist = True
datasource.inputs.ignore_exception = False
datasource.inputs.raise_on_empty = True
motcor_sltimes_wf.connect(subj_iterable, 'subject_id', datasource, 'subject_id')

# Create a Function node to rename output files with something more meaningful
getsubs = pe.Node(util.Function(input_names=['subject_id', 'mri_files'],
                                output_names=['subs'],
                                function=get_subs),
                  name='getsubs')
getsubs.inputs.ignore_exception = False
motcor_sltimes_wf.connect(subj_iterable, 'subject_id', getsubs, 'subject_id')
motcor_sltimes_wf.connect(datasource, 'mri_files', getsubs, 'mri_files')

# Extract the first volume of the first run as the reference 
extractref = pe.Node(fsl.ExtractROI(t_size=1),
                     iterfield=['in_file'],
                     name = "extractref")
motcor_sltimes_wf.connect(datasource, ('mri_files', pickfirst), extractref, 'in_file')
motcor_sltimes_wf.connect(datasource, ('mri_files', pickvol, 0, 'middle'), extractref, 't_min')
motcor_sltimes_wf.connect(extractref, 'roi_file', outputspec, 'reference')

if slice_timer is 'NIPY':
    # Simultaneous motion and slice timing correction with Nipy algorithm
    motion_sltime_correct = pe.MapNode(nipy.SpaceTimeRealigner(),
                                       name='motion_sltime_correct',
                                       iterfield = ['in_file', 'slice_times'])
    motion_sltime_correct.inputs.tr = 2.0
    motion_sltime_correct.inputs.slice_info = 2
    motion_sltime_correct.plugin_args = {'bsub_args': '-n %s' %os.environ['MKL_NUM_THREADS']}
    motion_sltime_correct.plugin_args = {'bsub_args': '-R "span[hosts=1]"'}
    motcor_sltimes_wf.connect(datasource, 'mri_files', motion_sltime_correct, 'in_file')
    motcor_sltimes_wf.connect(datasource, ('mri_files', calc_slicetimes, 2.0), motion_sltime_correct, 'slice_times')
    motcor_sltimes_wf.connect(motion_sltime_correct, 'par_file', outputspec, 'motion_parameters')
    motcor_sltimes_wf.connect(motion_sltime_correct, 'out_file', outputspec, 'motion_sltime_corrected_files')
elif slice_timer is 'FSL':
    # Motion correct functional runs to the reference (1st volume of 1st run)
    motion_correct =  pe.MapNode(fsl.MCFLIRT(interpolation = 'sinc',
                                             save_plots = True),
                                 name = 'motion_correct',
                                 iterfield = ['in_file'])
    motcor_sltimes_wf.connect(datasource, 'mri_files', motion_correct, 'in_file')
    motcor_sltimes_wf.connect(extractref, 'roi_file', motion_correct, 'ref_file')
    motcor_sltimes_wf.connect(motion_correct, 'par_file', outputspec, 'motion_parameters')
    motcor_sltimes_wf.connect(motion_correct, 'out_file', outputspec, 'motion_corrected_files')

    # Slice timing correction 
    #motion_sltime_correct = pe.MapNode(fsl.SliceTimer(),
    #                                   name = 'motion_sltime_correct',
    #                                   iterfield = ['in_file'])
    #motion_sltime_correct.inputs.time_repetition = 2.0
    #motion_sltime_correct.inputs.interleaved = True
    #motion_sltime_correct.inputs.output_type = 'NIFTI_GZ'
    #motcor_sltimes_wf.connect(motion_correct, 'out_file', motion_sltime_correct, 'in_file')
    #motcor_sltimes_wf.connect(motion_sltime_correct, 'slice_time_corrected_file', outputspec, 'motion_sltime_corrected_files')
elif slice_timer is 'AFNI':
    # Motion correct functional runs
    motion_correct = pe.MapNode(afni.Volreg(outputtype = 'NIFTI_GZ'),
                                name = 'motion_correct',
                                iterfield = ['in_file'])
    motcor_sltimes_wf.connect(datasource, 'mri_files', motion_correct, 'in_file')
    motcor_sltimes_wf.connect(extractref, 'roi_file', motion_correct, 'basefile')
    motcor_sltimes_wf.connect(motion_correct, 'oned_file', outputspec, 'motion_parameters')

    # Slice timing correction
    motion_sltime_correct = pe.MapNode(afni.TShift(outputtype = 'NIFTI_GZ'),
                                       name = 'motion_sltime_correct',
                                       iterfield = ['in_file'])
    motion_sltime_correct.inputs.tr = '2.0s'
    motion_sltime_correct.inputs.tpattern = 'altplus'
    motcor_sltimes_wf.connect(motion_correct, 'out_file', motion_sltime_correct, 'in_file')
    motcor_sltimes_wf.connect(motion_sltime_correct, 'out_file', outputspec, 'motion_sltime_corrected_files')

# Plot the estimated motion parameters
plot_motion = pe.MapNode(fsl.PlotMotionParams(in_source='fsl'),
                         name='plot_motion',
                         iterfield=['in_file'])
plot_motion.iterables = ('plot_type', ['rotations', 'translations'])
if slice_timer is 'NIPY':
    motcor_sltimes_wf.connect(motion_sltime_correct, 'par_file', plot_motion, 'in_file')
elif slice_timer is 'FSL':
    motcor_sltimes_wf.connect(motion_correct, 'par_file', plot_motion, 'in_file')
elif slice_timer is 'AFNI':
    # This may not work???
    motcor_sltimes_wf.connect(motion_correct, 'oned_file', plot_motion, 'in_file')
motcor_sltimes_wf.connect(plot_motion, 'out_file', outputspec, 'motion_plots')

# Save the relevant data into an output directory
datasink = pe.Node(nio.DataSink(), name="datasink")
datasink.inputs.base_directory = sink_dir
motcor_sltimes_wf.connect(subj_iterable, 'subject_id', datasink, 'container')
motcor_sltimes_wf.connect(outputspec, 'reference', datasink, 'preproc.ref')
motcor_sltimes_wf.connect(outputspec, 'motion_parameters', datasink, 'preproc.motion')
motcor_sltimes_wf.connect(outputspec, 'motion_corrected_files', datasink, 'preproc.func')
#motcor_sltimes_wf.connect(outputspec, 'motion_sltime_corrected_files', datasink, 'preproc.func')
motcor_sltimes_wf.connect(outputspec, 'motion_plots', datasink, 'preproc.motplots')
motcor_sltimes_wf.connect(getsubs, 'subs', datasink, 'substitutions')

# Run things and write crash files if necessary
#motcor_sltimes_wf.write_graph(graph2use='flat')
motcor_sltimes_wf.config['execution']['crashdump_dir'] = '/scratch/PSB6351_2017/crash/mattfeld/week5/nipype_crash'
motcor_sltimes_wf.base_dir = work_dir
motcor_sltimes_wf.run(plugin='LSF', plugin_args={'bsub_args': '-q PQ_madlab'})
motcor_sltimes_wf.write_graph()
