import argparse
import os
import shutil
from bids import BIDSLayout
from nipype.interfaces.utility import IdentityInterface
from nipype.pipeline import Workflow
from nipype import Node, Function
from nipype.interfaces.io import SelectFiles
from niworkflows.utils.misc import check_valid_fs_license
from petdeface.workflows.mideface import Mideface
from petdeface.workflows.utils.pet import create_weighted_average_pet
from nipype.interfaces.freesurfer import MRICoreg

__version__ = open(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                'version')).read()

def main(args): 
    """Main function for the PET Deface workflow."""

    if os.path.exists(args.bids_dir):
        if not args.skip_bids_validator:
            layout = BIDSLayout(args.bids_dir, validate=True)
        else:
            layout = BIDSLayout(args.bids_dir, validate=False)
    else:
        raise Exception('BIDS directory does not exist')
    
    if check_valid_fs_license() is not True:
        raise Exception('You need a valid FreeSurfer license to proceed!')
    
    if check_fsl_installed() is not True:
        raise Exception('FSL is not installed or sourced')
    
    # Get all PET files
    if args.participant_label is None:
        args.participant_label = layout.get(suffix='pet', target='subject', return_type='id')

    # create output derivatives directory
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # create output directory for this pipeline
    pipeline_dir = os.path.join(args.output_dir, 'petdeface')
    if not os.path.exists(pipeline_dir):
        os.makedirs(pipeline_dir)

    infosource = Node(IdentityInterface(
                        fields = ['subject_id','session_id']),
                        name = "infosource")
    
    sessions = layout.get_sessions()
    if sessions:
        infosource.iterables = [('subject_id', args.participant_label),
                                ('session_id', sessions)]
    else:
        infosource.iterables = [('subject_id', args.participant_label)]

    templates = {'t1w_file': 'sub-{subject_id}/anat/*_T1w.[n]*' if not sessions else 'sub-{subject_id}/ses-{session_id}/anat/*_T1w.[n]*',
                'pet_file': 'sub-{subject_id}/pet/*_pet.[n]*' if not sessions else 'sub-{subject_id}/ses-{session_id}/pet/*_pet.[n]*',
                'json_file': 'sub-{subject_id}/pet/*_pet.json' if not sessions else 'sub-{subject_id}/ses-{session_id}/pet/*_pet.json'}
           
    selectfiles = Node(SelectFiles(templates, 
                               base_directory = args.bids_dir), 
                               name = "select_files")

    substitutions = [('_subject_id', 'sub'), ('_session_id_', 'ses')]
    subjFolders = [('sub-%s' % (sub), 'sub-%s' % (sub))
               for sub in layout.get_subjects()] if not sessions else [('sub-%s_ses-%s' % (sub, ses), 'sub-%s/ses-%s' % (sub, ses))
               for ses in layout.get_sessions()
               for sub in layout.get_subjects()]

    substitutions.extend(subjFolders)

    # clean up and create derivatives directories
    if args.output_dir is None:
        output_dir = os.path.join(args.bids_dir,'derivatives','petdeface')
    else:
        output_dir = args.output_dir

    # Define nodes for hmc workflow

    deface_t1w = Node(Mideface(out_file = 't1w_defaced.nii.gz',
                               out_facemask = 'face.mask.mgz',
                               odir = '.'),
                 name = 'deface_t1w')
    
    coreg_pet_to_t1w = Node(MRICoreg(),
                       name = 'coreg_pet_to_t1w')
    
    create_time_weighted_average = Node(Function(input_names = ['pet_file', 'bids_dir'],
                                            output_names = ['out_file'],
                                            function = create_weighted_average_pet),
                                   name = 'create_weighted_average_pet')
    
    create_time_weighted_average.inputs.bids_dir = args.bids_dir

    deface_pet = Node(Mideface(out_file = 'pet_defaced.nii.gz',
                               out_facemask = 'face.mask.mgz',
                               odir = '.'),
                 name = 'deface_pet')
    
    create_apply_str_node = Node(Function(input_names=['t1w_defaced','facemask', 'lta_file', 'pet_file', 'bids_dir'],
                                        output_names=['apply_str'],
                                        function=create_apply_str),
                               name='create_apply_str')
    create_apply_str_node.inputs.bids_dir = args.bids_dir
    
    workflow = Workflow(name='deface_pet_workflow', base_dir=args.bids_dir)
    workflow.config['execution']['remove_unnecessary_outputs'] = 'false'
    workflow.connect([(infosource, selectfiles, [('subject_id', 'subject_id'),('session_id', 'session_id')]), 
                        (selectfiles, deface_t1w, [('t1w_file', 'in_file')]),
                        (selectfiles, create_time_weighted_average, [('pet_file', 'pet_file')]),
                        (selectfiles, coreg_pet_to_t1w, [('t1w_file', 'reference_file')]),
                        (create_time_weighted_average, coreg_pet_to_t1w, [('out_file', 'source_file')]),
                        (deface_t1w, create_apply_str_node, [('out_facemask', 'facemask')]),
                        (coreg_pet_to_t1w, create_apply_str_node, [('out_lta_file', 'lta_file')]),
                        (selectfiles, create_apply_str_node, [('pet_file', 'pet_file')]),
                        (deface_t1w, create_apply_str_node, [('out_file', 't1w_defaced')]),
                        (create_apply_str_node, deface_pet, [('apply_str', 'apply')])
                    ])

    wf = workflow.run(plugin='MultiProc', plugin_args={'n_procs' : int(args.n_procs)})

    # remove temp outputs
    shutil.rmtree(os.path.join(args.bids_dir, 'deface_pet_workflow'))

def create_apply_str(t1w_defaced, pet_file, facemask, lta_file, bids_dir):
    """Create string to be used for the --apply flag for defacing PET using mideface."""
    from pathlib import Path
    from bids.layout import BIDSLayout

    layout = BIDSLayout(bids_dir)
    entities = layout.parse_file_entities(pet_file)

    subject = entities['subject']
    session = entities['session']
    out_file = f"{bids_dir}/derivatives/petdeface/sub-{subject}/ses-{session}/pet/sub-{subject}_ses-{session}_desc-defaced_pet.nii.gz"

    out_lta_file = f"{bids_dir}/derivatives/petdeface/sub-{subject}/ses-{session}/pet/sub-{subject}_ses-{session}_desc-pet2anat_pet.lta"
    out_mask_file = f"{bids_dir}/derivatives/petdeface/sub-{subject}/ses-{session}/anat/sub-{subject}_ses-{session}_desc-defaced_pet_mask.nii.gz"
    out_t1w_defaced = f"{bids_dir}/derivatives/petdeface/sub-{subject}/ses-{session}/anat/sub-{subject}_ses-{session}_desc-defaced_T1w.nii.gz"

    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    Path(out_lta_file).parent.mkdir(parents=True, exist_ok=True)
    Path(out_mask_file).parent.mkdir(parents=True, exist_ok=True)
    Path(out_t1w_defaced).parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(t1w_defaced, out_t1w_defaced)
    shutil.copyfile(lta_file, out_lta_file)
    shutil.copyfile(facemask, out_mask_file)

    apply_str = f"{pet_file} {facemask} {lta_file} {out_file}"

    return apply_str

def check_fsl_installed():
    try:
        fsl_home = os.environ['FSLDIR']
        if fsl_home:
            print("FSL is installed at:", fsl_home)
            return True
    except KeyError:
        print("FSL is not installed or FSLDIR environment variable is not set.")
        return False


if __name__ == '__main__': 
    parser = argparse.ArgumentParser(description='BIDS App for PET deface workflow')
    parser.add_argument('--bids_dir', required=True,  help='The directory with the input dataset '
                    'formatted according to the BIDS standard.')
    parser.add_argument('--output_dir', required=False, help='The directory where the output files '
                    'should be stored. If you are running group level analysis '
                    'this folder should be prepopulated with the results of the'
                    'participant level analysis.')
    parser.add_argument('--analysis_level', default='participant', help='Level of the analysis that will be performed. '
                    'Multiple participant level analyses can be run independently '
                    '(in parallel) using the same output_dir.',
                    choices=['participant', 'group'])
    parser.add_argument('--participant_label', help='The label(s) of the participant(s) that should be analyzed. The label '
                   'corresponds to sub-<participant_label> from the BIDS spec '
                   '(so it does not include "sub-"). If this parameter is not '
                   'provided all subjects should be analyzed. Multiple '
                   'participants can be specified with a space separated list.',
                   nargs="+", default=None)
    parser.add_argument('--n_procs', help='Number of processors to use when running the workflow', default=2)
    parser.add_argument('--skip_bids_validator', help='Whether or not to perform BIDS dataset validation',
                   action='store_true')
    parser.add_argument('-v', '--version', action='version',
                    version='PETDeface BIDS-App version {}'.format(__version__))
    
    args = parser.parse_args() 
    
    main(args)
