def create_weighted_average_pet(fin, json_file, fout, frames=None):
    
    """
    Create a time-weighted average of dynamic PET data using mid-frames
    
    Arguments
    ---------
    fin: string
        path to input dynamic PET volume
    fout: string
        path to output average volume
    frames: list of integers
        list of frames to be used for computing the average (indices are 0-based)
    """     
      
    if not isfile(fout):
        img = nib.load(fin)        
        data = img.get_fdata()

        frames_start, frames_duration = get_timing(json_file)
        
        # Check that the specified frame interval, if any, is valid
        if frames is None:
            frames = range(data.shape[-1])
        else:
            if frames[0] < 0:
                raise ValueError('The indice of of first frame needs to be equal or larger than 0')
            if frames[-1] >= data.shape[-1]:
                raise ValueError('The indice of of last frame needs to less than %i' % data.shape[-1])

        mid_frames = frames_start + frames_duration/2
        wavg = np.trapz(data[..., frames], dx=np.diff(mid_frames[frames]), axis=3)/np.sum(mid_frames)
        print('Saving average to ' + fout)
        nib.save(nib.Nifti1Image(wavg, img.affine), fout)
    else:
        print('File ' + fout + ' already exists. Skipping.')