.. petdeface documentation master file, created by
   sphinx-quickstart on Wed Dec  6 14:28:30 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to petdeface's documentation!
=====================================

petdeface is a nipype implementation of an anatomical MR and PET defacing pipeline for BIDS datasets. 
This is a working prototype, in active development denoted by the 0.x.x version number. 

However, it is functional and can be used to deface PET and MR data as well as co-register the two modalities. 
Use is encouraged and feedback via Github issues or email to openneuropet@gmail.com is more than welcome. 
As is often the case, this medical research software is constrained to testing on data that its developers 
have access to.

This software can be installed via source or via pip from PyPi with ``pip install petdeface``

**NOTE:** This project is currently in beta release, some features listed below may 
not be available for version numbers < 1.0.0

.. toctree::
   installation
   modules
   usage
   :maxdepth: 2
   :caption: Contents:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Citations
---------

1. Dale A, Fischl B, Sereno MI. Cortical Surface-Based Analysis: I. Segmentation and Surface Reconstruction.
   Neuroimage. 1999;9(2):179–94. doi:10.1006/nimg.1998.0395.
2. Fischl B. FreeSurfer. Neuroimage. 2012 Aug 15;62(2):774-81. doi: 10.1016/j.neuroimage.2012.01.021.
   Epub 2012 Jan 10. PMID: 22248573; PMCID: PMC3685476.
3. Stefano Cerri, Douglas N. Greve, Andrew Hoopes, Henrik Lundell, Hartwig R. Siebner, Mark Mühlau, Koen Van Leemput,
   An open-source tool for longitudinal whole-brain and white matter lesion segmentation,
   NeuroImage: Clinical, Volume 38, 2023, 103354, ISSN 2213-1582, https://doi.org/10.1016/j.nicl.2023.103354.
   (https://www.sciencedirect.com/science/article/pii/S2213158223000438)
4. Gorgolewski, Krzysztof J. ; Esteban, Oscar ; Burns, Christopher ; Ziegler, Erik ; Pinsard, Basile ; Madison, Cindee ;
   Waskom, Michael ; Ellis, David Gage ; Clark, Dav ; Dayan, Michael ; Manhães-Savio, Alexandre ;
   Notter, Michael Philipp ; Johnson, Hans ; Dewey, Blake E ; Halchenko, Yaroslav O. ; Hamalainen, Carlo ;
   Keshavan, Anisha ; Clark, Daniel ; Huntenburg, Julia M. ; Hanke, Michael ; Nichols, B. Nolan ; Wassermann , Demian ;
   Eshaghi, Arman ; Markiewicz, Christopher ; Varoquaux, Gael ; Acland, Benjamin ; Forbes, Jessica ; Rokem, Ariel ;
   Kong, Xiang-Zhen ; Gramfort, Alexandre ; Kleesiek, Jens ; Schaefer, Alexander ; Sikka, Sharad ;
   Perez-Guevara, Martin Felipe ; Glatard, Tristan ; Iqbal, Shariq ; Liu, Siqi ; Welch, David ; Sharp, Paul ;
   Warner, Joshua ; Kastman, Erik ; Lampe, Leonie ; Perkins, L. Nathan ; Craddock, R. Cameron ; Küttner, René ;
   Bielievtsov, Dmytro ; Geisler, Daniel ; Gerhard, Stephan ; Liem, Franziskus ; Linkersdörfer, Janosch ;
   Margulies, Daniel S. ; Andberg, Sami Kristian ; Stadler, Jörg ; Steele, Christopher John ; Broderick, William ;
   Cooper, Gavin ; Floren, Andrew ; Huang, Lijie ; Gonzalez, Ivan ; McNamee, Daniel ; Papadopoulos Orfanos, Dimitri ;
   Pellman, John ; Triplett, William ; Ghosh, Satrajit (2016). Nipype: a flexible, lightweight and extensible
   neuroimaging data processing framework in Python. 0.12.0-rc1. Zenodo. 10.5281/zenodo.50186
