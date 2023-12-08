.. _installation:

Installation
============

.. _PyPi: https://pypi.org/project/petdeface/

PETdeface can be installed via PyPi_::

    pip install petdeface

Or cloned and installed from source::

    git clone https://github.com/openneuropet/petdeface.git
    cd petdeface
    poetry build
    pip install dist/petdeface-<X.X.X>-py3-none-any.whl 
    # where X.X.X is the version number of the generated file

Dependencies
------------

- FreeSurfer_ and MiDeFAce_ >= 7.3

.. _FreeSurfer: https://surfer.nmr.mgh.harvard.edu/ 
.. _MiDeFace: https://surfer.nmr.mgh.harvard.edu/fswiki/MiDeFace

- Nipype_ >= 1.6.0

.. _Nipype: https://nipype.readthedocs.io/en/latest/

Optional Dependencies
---------------------

- Docker_

.. _Docker: https://www.docker.com/