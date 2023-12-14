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
    Command line arguments for mideface defined as traits for nipype CommandLineInputSpec.
    Arguments are defined here and where necessary defaulted with string values to make subsequent
    steps in the pipeline possible. E.g. defaced output files are denoted with the '_defaced' suffix
    to differentiate them from the original input files.


    :param CommandLineInputSpec: nipype CommandLineInputSpec
    :type CommandLineInputSpec: nipype.interfaces.base.CommandLineInputSpec
    """

    #: volume to deface,  *type(nipype.interfaces.base.File)*
    in_file = File(desc="Volume to deface", exists=True, argstr="--i %s")
    #: defaced input, ``--o``, *type(nipype.interfaces.base.File)*
    out_file = File(
        desc="Defaced input",
        argstr="--o %s",
        name_source="in_file",
        name_template="%s_defaced",
        keep_extension=True,
    )
    #: facemask, ``--facemask``, *type(nipype.interfaces.base.File)*
    out_facemask = File(
        desc="Facemask",
        argstr="--facemask %s",
        name_source="in_file",
        name_template="%s_defacemask",
        keep_extension=True,
    )
    #: output directory (turns on PostHeadSurf), ``--odir``, *type(nipype.interfaces.base.Directory)*
    odir = Directory(
        desc="Output directory (turns on PostHeadSurf)",
        argstr="--odir %s",
    )
    #: xmask (exclusion mask), ``--xmask``, *type(nipype.interfaces.base.File)*
    xmask = File(
        desc="Exclusion mask",
        argstr="--xmask %s",
        exists=True,
    )
    #: ndilations segment input using samseg (14GB, +~20-40min) ``--xmask-samseg``, *type(nipype.traits.Int)*
    xmask_samseg = traits.Int(
        desc="Segment input using samseg (14GB, +~20-40min)",
        argstr="--xmask-samseg %d",
    )
    #: configure samseg ``--samseg-json``, *type(nipype.interfaces.base.File)*
    samseg_json = File(
        desc="Configure samseg",
        argstr="--samseg-json %s",
        exists=True,
    )
    #: configure samseg to run quickly; sets ndil=1 (default), ``--samseg-fast``, *type(nipype.traits.Bool)*
    samseg_fast = traits.Bool(
        desc="Configure samseg to run quickly; sets ndil=1 (default)",
        argstr="--samseg-fast",
    )
    #: do NOT configure samseg to run quickly, ``--no-samseg-fast``, *type(nipype.traits.Bool)*
    no_samseg_fast = traits.Bool(
        desc="Do NOT configure samseg to run quickly",
        argstr="--no-samseg-fast",
    )
    #: initialize samseg with reg (good in case samseg reg fails), ``--init-reg reg.lta``, *type(nipype.interfaces.base.File)*
    init_reg = File(
        desc="Initialize samseg with reg (good in case samseg reg fails)",
        argstr="--init-reg %s",
        exists=True,
    )
    #: ndilations : segment input using synthseg (35GB, +~20min), ``--xmask-synthseg``, *type(nipype.traits.Int)*
    xmask_synthseg = traits.Int(
        desc="Segment input using synthseg (35GB, +~20min)",
        argstr="--xmask-synthseg %d",
    )
    #: constIn constOut, ``--fill-const``, *type(nipype.traits.Tuple)*
    fill_const = traits.Tuple(
        traits.Float,
        traits.Float,
        desc="Fill constants",
        argstr="--fill-const %f %f",
    )
    #: fill with zero, ``--fill-zero``, *type(nipype.traits.Bool)*
    fill_zero = traits.Bool(
        desc="Fill with zero",
        argstr="--fill-zero",
    )
    #: do not include ears in the defacing, ``--no-ears``, *type(nipype.traits.Bool)*
    no_ears = traits.Bool(
        desc="Do not include ears in the defacing",
        argstr="--no-ears",
    )
    #: include back of head in the defacing, ``--back-of-head``, *type(nipype.traits.Bool)*
    back_of_head = traits.Bool(
        desc="Include back of head in the defacing",
        argstr="--back-of-head",
    )
    #: include forehead in the defacing (risks removing brain), ``--forehead``, *type(nipype.traits.Bool)*
    forehead = traits.Bool(
        desc="Include forehead in the defacing (risks removing brain)",
        argstr="--forehead",
    )
    #: take pics (--no-pics), ``--pics``, *type(nipype.traits.Bool)*
    pics = traits.Bool(
        desc="Take pics",
        argstr="--pics",
    )
    #: do not take pics, ``--no-pics``, *type(nipype.traits.Bool)*
    no_pics = traits.Bool(
        desc="Do not take pics",
        argstr="--no-pics",
    )
    #: codename : embed codename in pics, ``--code``, *type(nipype.traits.Str)*
    code = traits.Str(
        desc="Embed codename in pics",
        argstr="--code %s",
    )
    #: /path/to/convert : path to imagemagik convert binary (for pics), ``--imconvert``, *type(nipype.interfaces.base.File)*
    imconvert = File(
        desc="Path to ImageMagick convert binary (for pics)",
        argstr="--imconvert %s",
        exists=True,
    )
    #: do not make a head surface after defacing, ``--no-post``, *type(nipype.traits.Bool)*
    no_post = traits.Bool(
        desc="Do not make a head surface after defacing",
        argstr="--no-post",
    )
    #: number of threads, ``--threads``, *type(nipype.traits.Int)*
    threads = traits.Int(
        desc="Number of threads",
        argstr="--threads %d",
    )
    #: force reprocessing (not applicable if --odir has not been used), ``--force``, *type(nipype.traits.Bool)*
    force = traits.Bool(
        desc="Force reprocessing (not applicable if --odir has not been used)",
        argstr="--force",
    )
    #: use nifti format as output (only when output files are not specified), ``--nii``, *type(nipype.traits.Bool)*
    nii = traits.Bool(
        desc="Use NIfTI format as output (only when output files are not specified)",
        argstr="--nii",
    )
    #: use compressed nifti format as output (only when output files are not specified), ``--nii.gz``, *type(nipype.traits.Bool)*
    nii_gz = traits.Bool(
        desc="Use compressed NIfTI format as output (only when output files are not specified)",
        argstr="--nii.gz",
    )
    #: use compressed mgh format as output (default), ``--mgz``, *type(nipype.traits.Bool)*
    mgz = traits.Bool(
        desc="Use compressed MGH format as output (default)",
        argstr="--mgz",
    )
    #: atlasdir, ``--atlas``, *type(nipype.interfaces.base.Directory)*
    atlas = Directory(
        desc="Atlas directory",
        argstr="--atlas %s",
        exists=True,
    )
    #: expert options file, ``--expert``, *type(nipype.interfaces.base.File)*
    expert = File(
        desc="Expert options file",
        argstr="--expert %s",
        exists=True,
    )
    #: set Xvfb display number for taking pics, ``--display``, *type(nipype.traits.Int)*
    display = traits.Int(
        desc="Set Xvfb display number for taking pics",
        argstr="--display %d",
    )
    #: input defaced : check whether a volume has been defaced, ``--check``, *type(nipype.traits.Tuple)*
    check = traits.Tuple(
        File,
        File,
        desc="Check whether a volume has been defaced",
        argstr="--check %s %s",
    )


class MidefaceOutputSpec(TraitedSpec):
    """
    Set of traits corresponding to the desired mideface output files for this petdefacing pipeline.

    :param TraitedSpec: nipype TraitedSpec class
    :type TraitedSpec: nipype.interfaces.base.TraitedSpec
    """

    #: trait for defaced input, ``--o``, *type(nipype.interfaces.base.File)*
    out_file = File(desc="Defaced input", exists=True)
    #: trait for facemask, ``--facemask``, *type(nipype.interfaces.base.File)*
    out_facemask = File(desc="Facemask", exists=True)
    #: trait for before defacing picture
    out_before_pic = File(desc="before pic", exists=True)
    #: trait for after defacing picture
    out_after_pic = File(desc="after pic", exists=True)


class Mideface(CommandLine):
    """
    nipype implementation of Freesurfer's MiDeface command line tool. This class is used to deface an anatomical
    image. Inherits from a nipype CommandLine class and uses the MidefaceInputSpec and MidefaceOutputSpec traits
    as input and output.

    :param CommandLine: Inherits from nipype CommandLine class
    :type CommandLine: nipype.interfaces.base.CommandLine
    """

    #: command to run, defaults to "mideface"
    _cmd = "mideface"
    #: mideface inputs defined as traits in MidefaceInputSpec
    input_spec = MidefaceInputSpec
    #: mideface outputs defined as traits in MidefaceOutputSpec
    output_spec = MidefaceOutputSpec

    def _list_outputs(self):
        """
        Overrides default nipype CommandLine _list_outputs method to help in collecting
        additional outputs from mideface. Namely, this method collects the before pic and after pic.

        :return: outputs from mideface
        :rtype: dict
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
    nipype CommandLineInputSpec for running mideface with the ``--apply`` flag to apply a facemask to a volume.

    :param CommandLineInputSpec: nipype CommandLineInputSpec class to inherit from
    :type CommandLineInputSpec: nipype.interfaces.base.CommandLineInputSpec
    """

    #: volume to deface,  *type(nipype.interfaces.base.File)*
    in_file = File(
        desc="Volume to deface",
        exists=True,
        position=1,
        argstr="%s",
    )
    #: facemask to apply to volume to deface, *type(nipype.interfaces.base.File)*
    facemask = File(
        desc="Facemask",
        exists=True,
        position=2,
        argstr="%s",
    )
    #: registration matrix lta file, *type(nipype.interfaces.base.File)*
    lta_file = File(
        desc="Registration matrix lta file",
        exists=True,
        position=3,
        argstr="%s",
    )
    #: defaced input, ``--o``, *type(nipype.interfaces.base.File)*
    out_file = File(
        desc="Defaced input",
        position=4,
        argstr="%s",
        name_source="in_file",
        name_template="%s_defaced",
        keep_extension=True,
    )


class ApplyMidefaceOutputSpec(TraitedSpec):
    """
    nipype TraitedSpec class for ApplyMideface. Defines the output trait for ApplyMideface, which
    is the defaced image that a facemask has been applied to.

    :param TraitedSpec: nipype TraitedSpec class to inherit from
    :type TraitedSpec: nipype.interfaces.base.TraitedSpec
    """

    out_file = File(desc="Defaced input", exists=True)


class ApplyMideface(CommandLine):
    """
    Runs mideface with the ``--apply`` flag to apply a facemask to a volume, uses inputs and outputs
    definde in ApplyMidefaceInputSpec and ApplyMidefaceOutputSpec respectively.

    This class is used to deface a pet image using a previously created facemask from an anatomical (T1w) image.
    Requires petdeface.Mideface to have been run previously run and an input PET image.

    :param CommandLine: nipype CommandLine class
    :type CommandLine: nipype.interfaces.base.CommandLine
    """

    #: command to apply
    _cmd = "mideface --apply"
    #: apply mideface inputs defined as traits in ApplyMidefaceInputSpec
    input_spec = ApplyMidefaceInputSpec
    #: apply mideface outputs defined as traits in ApplyMidefaceOutputSpec
    output_spec = ApplyMidefaceOutputSpec
