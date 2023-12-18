import os

import nibabel as nib
import numpy as np
from nipype.interfaces.base import BaseInterface
from nipype.interfaces.base import BaseInterfaceInputSpec
from nipype.interfaces.base import File
from nipype.interfaces.base import TraitedSpec
from nipype.utils.filemanip import split_filename
from niworkflows.interfaces.bids import ReadSidecarJSON


class WeightedAverageInputSpec(BaseInterfaceInputSpec):
    pet_file = File(exists=True, desc="Dynamic PET", mandatory=True)


class WeightedAverageOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="Time-weighted average of dynamic PET")


class WeightedAverage(BaseInterface):
    """
    Create a time-weighted average of dynamic PET data using mid-frames.

    :param BaseInterface: nipype BaseInterface class to inherit from
    :type BaseInterface: nipype.interfaces.base.BaseInterface
    :return: none
    :rtype: none
    """

    #: nipype input specification for the interface
    input_spec = WeightedAverageInputSpec
    #: nipype output specification for the interface
    output_spec = WeightedAverageOutputSpec

    def _run_interface(self, runtime):
        """
        Loads a pet file and calculates the time-weighted average from its frames.
        Saves average into nifti file with _desc-wavg_pet suffix.

        :param runtime:
        :type runtime:
        """
        pet_file = self.inputs.pet_file
        bids_dir = os.path.dirname(pet_file)

        img = nib.load(pet_file)
        data = img.get_fdata()

        meta = ReadSidecarJSON(
            in_file=pet_file, bids_dir=bids_dir, bids_validate=False
        ).run()

        frames_start = np.array(meta.outputs.out_dict["FrameTimesStart"])
        frames_duration = np.array(meta.outputs.out_dict["FrameDuration"])

        mid_frames = frames_start + frames_duration / 2
        wavg = np.trapz(data, x=mid_frames) / (mid_frames[-1] - mid_frames[0])

        _, base, ext = split_filename(pet_file)
        out_name = base.replace("_pet", "_desc-wavg_pet")
        out_file = out_name + ext
        nib.save(nib.Nifti1Image(wavg, img.affine), out_file)

    def _list_outputs(self):
        """
        Returns the output of the interface.

        :return: outputs calculated in _run_interface
        :rtype: dict
        """
        outputs = self._outputs().get()
        pet_file = self.inputs.pet_file
        _, base, ext = split_filename(pet_file)

        out_name = base.replace("_pet", "_desc-wavg_pet")
        out_file = os.path.abspath(out_name + ext)

        outputs["out_file"] = out_file

        return outputs
