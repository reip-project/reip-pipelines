from distutils.core import setup, Extension
import numpy

# To install SWIG:
# sudo apt install swig

# To compile/install labeler:
# python3 setup.py build_ext --inplace

setup(ext_modules=[Extension("_labeler_module",
      sources=["labeler.c", "labeler.i"],
      include_dirs=[numpy.get_include()])])
