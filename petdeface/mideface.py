from nipype.interfaces.base import CommandLine
from nipype.interfaces.base import CommandLineInputSpec
from nipype.interfaces.base import Directory
from nipype.interfaces.base import File
from nipype.interfaces.base import TraitedSpec
from nipype.interfaces.base import traits
from nipype.interfaces.base import isdefined
import os


class MidefaceInputSpec(CommandLineInputSpec):
    """
    _summary_

    :param CommandLineInputSpec: _description_
    :type CommandLineInputSpec: _type_
    """
    in_file = File(desc="Volume to deface", exists=True, argstr="--i %s")
    out_file = File(
        desc="Defaced input",
        argstr="--o %s",
        name_source="in_file",
        name_template="%s_defaced",
        keep_extension=True,
    )
    out_facemask = File(
        desc="Facemask",
        argstr="--facemask %s",
        name_source="in_file",
        name_template="%s_defacemask",
        keep_extension=True,
    )
    odir = Directory(
        desc="Output directory (turns on PostHeadSurf)",
        argstr="--odir %s",
    )
    xmask = File(
        desc="Exclusion mask",
        argstr="--xmask %s",
        exists=True,
    )
    xmask_samseg = traits.Int(
        desc="Segment input using samseg (14GB, +~20-40min)",
        argstr="--xmask-samseg %d",
    )
    samseg_json = File(
        desc="Configure samseg",
        argstr="--samseg-json %s",
        exists=True,
    )
    samseg_fast = traits.Bool(
        desc="Configure samseg to run quickly; sets ndil=1 (default)",
        argstr="--samseg-fast",
    )
    no_samseg_fast = traits.Bool(
        desc="Do NOT configure samseg to run quickly",
        argstr="--no-samseg-fast",
    )
    init_reg = File(
        desc="Initialize samseg with reg (good in case samseg reg fails)",
        argstr="--init-reg %s",
        exists=True,
    )
    xmask_synthseg = traits.Int(
        desc="Segment input using synthseg (35GB, +~20min)",
        argstr="--xmask-synthseg %d",
    )
    fill_const = traits.Tuple(
        traits.Float,
        traits.Float,
        desc="Fill constants",
        argstr="--fill-const %f %f",
    )
    fill_zero = traits.Bool(
        desc="Fill with zero",
        argstr="--fill-zero",
    )
    no_ears = traits.Bool(
        desc="Do not include ears in the defacing",
        argstr="--no-ears",
    )
    back_of_head = traits.Bool(
        desc="Include back of head in the defacing",
        argstr="--back-of-head",
    )
    forehead = traits.Bool(
        desc="Include forehead in the defacing (risks removing brain)",
        argstr="--forehead",
    )
    pics = traits.Bool(
        desc="Take pics",
        argstr="--pics",
    )
    no_pics = traits.Bool(
        desc="Do not take pics",
        argstr="--no-pics",
    )
    code = traits.Str(
        desc="Embed codename in pics",
        argstr="--code %s",
    )
    imconvert = File(
        desc="Path to ImageMagick convert binary (for pics)",
        argstr="--imconvert %s",
        exists=True,
    )
    no_post = traits.Bool(
        desc="Do not make a head surface after defacing",
        argstr="--no-post",
    )
    threads = traits.Int(
        desc="Number of threads",
        argstr="--threads %d",
    )
    force = traits.Bool(
        desc="Force reprocessing (not applicable if --odir has not been used)",
        argstr="--force",
    )
    nii = traits.Bool(
        desc="Use NIfTI format as output (only when output files are not specified)",
        argstr="--nii",
    )
    nii_gz = traits.Bool(
        desc="Use compressed NIfTI format as output (only when output files are not specified)",
        argstr="--nii.gz",
    )
    mgz = traits.Bool(
        desc="Use compressed MGH format as output (default)",
        argstr="--mgz",
    )
    atlas = Directory(
        desc="Atlas directory",
        argstr="--atlas %s",
        exists=True,
    )
    expert = File(
        desc="Expert options file",
        argstr="--expert %s",
        exists=True,
    )
    display = traits.Int(
        desc="Set Xvfb display number for taking pics",
        argstr="--display %d",
    )
    check = traits.Tuple(
        File,
        File,
        desc="Check whether a volume has been defaced",
        argstr="--check %s %s",
    )


class MidefaceOutputSpec(TraitedSpec):
    """
    _summary_

    :param TraitedSpec: _description_
    :type TraitedSpec: _type_
    """
    out_file = File(desc="Defaced input", exists=True)
    out_facemask = File(desc="Facemask", exists=True)
    out_before_pic = File(desc="before pic", exists=True)
    out_after_pic = File(desc="after pic", exists=True)


class Mideface(CommandLine):
    """
    _summary_

    :param CommandLine: _description_
    :type CommandLine: _type_
    :return: _description_
    :rtype: _type_
    """
    _cmd = "mideface"
    input_spec = MidefaceInputSpec
    output_spec = MidefaceOutputSpec

    def _list_outputs(self):
        """
        _summary_

        :return: _description_
        :rtype: _type_
        """
        metadata = dict(name_source=lambda t: t is not None)
        traits = self.inputs.traits(**metadata)
        if traits:
            outputs = self.output_spec().trait_get()
            for name, trait_spec in list(traits.items()):
                out_name = name
                if trait_spec.output_name is not None:
                    out_name = trait_spec.output_name
                fname = self._filename_from_source(name)
                if isdefined(fname):
                    outputs[out_name] = os.path.abspath(fname)
            if (
                self.inputs.pics is True
                and self.inputs.odir is not None
                and self.inputs.code is not None
            ):
                outputs["out_before_pic"] = os.path.abspath(
                    f"{self.inputs.odir}/{self.inputs.code}.face-before.png"
                )
                outputs["out_after_pic"] = os.path.abspath(
                    f"{self.inputs.odir}/{self.inputs.code}.face-after.png"
                )
            return outputs


class ApplyMidefaceInputSpec(CommandLineInputSpec):
    """
    _summary_

    :param CommandLineInputSpec: _description_
    :type CommandLineInputSpec: _type_
    """
    in_file = File(
        desc="Volume to deface",
        exists=True,
        position=1,
        argstr="%s",
    )
    facemask = File(
        desc="Facemask",
        exists=True,
        position=2,
        argstr="%s",
    )
    lta_file = File(
        desc="Registration matrix lta file",
        exists=True,
        position=3,
        argstr="%s",
    )
    out_file = File(
        desc="Defaced input",
        position=4,
        argstr="%s",
        name_source="in_file",
        name_template="%s_defaced",
        keep_extension=True,
    )


class ApplyMidefaceOutputSpec(TraitedSpec):
    out_file = File(desc="Defaced input", exists=True)


class ApplyMideface(CommandLine):
    """
    _summary_

    :param CommandLine: _description_
    :type CommandLine: _type_
    """
    _cmd = "mideface --apply"
    input_spec = ApplyMidefaceInputSpec
    output_spec = ApplyMidefaceOutputSpec
