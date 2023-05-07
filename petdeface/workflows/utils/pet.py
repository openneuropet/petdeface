import json

def create_weighted_average_pet(pet_file, json_file):
    
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

    frames_start, frames_duration = get_timing(json_file)

    mid_frames = frames_start + frames_duration/2
    wavg = np.trapz(data[..., frames], dx=np.diff(mid_frames[frames]), axis=3)/np.sum(mid_frames)

    out_file = pet_file.replace('.nii.gz', '_wavg.nii.gz')
    nib.save(nib.Nifti1Image(wavg, img.affine), out_file)

    return out_file

def get_timing(json_file):
    
    """
    Get timing information from PET json file
    
    Arguments
    ---------
    json_file: string
        path to PET json file containing timing information
    """     
    
    with open(json_file, 'r') as f:
        json_data = json.load(f)
    
    frames_start = np.array(json_data['FrameTimesStart'])
    frames_duration = np.array(json_data['FrameDuration'])
    
    return frames_start, frames_duration