import os
from bids import BIDSLayout
from nipype.interfaces.base import (
    TraitedSpec,
    CommandLineInputSpec,
    CommandLine,
    File,
    Directory,
    traits,
)

class MidefaceInputSpec(CommandLineInputSpec):
    in_file = File(
        desc="Volume to deface",
        exists=True,
        argstr="--i %s",
    )
    out_file = File(
        desc="Defaced input",
        argstr="--o %s",
        name_source=["in_file"],
        name_template="%s_defaced",
        output_name="out_file",
    )
    out_facemask = File(
        desc="Facemask",
        argstr="--facemask %s",
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
        traits.Float, traits.Float,
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
    apply = traits.Str(
        desc="Apply midface output to a second volume",
        argstr="--apply %s",
    )
    check = traits.Tuple(
        File, File,
        desc="Check whether a volume has been defaced",
        argstr="--check %s %s",
    )

class MidefaceOutputSpec(TraitedSpec):
    out_file = File(desc="Defaced input")
    out_facemask = File(desc="Facemask")

class Mideface(CommandLine):
    _cmd = "mideface"
    input_spec = MidefaceInputSpec
    output_spec = MidefaceOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        outputs["out_facemask"] = os.path.abspath(self.inputs.out_facemask)
        return outputs
   
