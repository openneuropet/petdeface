import json
from niworkflows.interfaces.bids import ReadSidecarJSON
import nibabel as nib
import numpy as np

def create_weighted_average_pet(pet_file, bids_dir):
    
    """
    Create a time-weighted average of dynamic PET data using mid-frames
    
    Arguments
    ---------
    pet_file: string
        path to input dynamic PET volume
    json_file: string
        path to PET json file containing timing information
    """     
      
    img = nib.load(pet_file)        
    data = img.get_fdata()

    meta = ReadSidecarJSON(in_file = pet_file, 
                           bids_dir = bids_dir, 
                           bids_validate = False).run()

    frames_start = np.array(meta.outputs.out_dict['FrameTimesStart'])
    frames_duration = np.array(meta.outputs.out_dict['FrameDuration'])

    frames = range(data.shape[-1])

    mid_frames = frames_start + frames_duration/2
    wavg = np.trapz(data[..., frames], dx=np.diff(mid_frames[frames]), axis=3)/np.sum(mid_frames)

    out_file = pet_file.replace('_pet.', '_desc-wavg_pet.')
    nib.save(nib.Nifti1Image(wavg, img.affine), out_file)

    return out_file