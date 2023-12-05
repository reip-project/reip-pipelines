

  

# Installation of REIP SDK on NVIDIA Jetson

  

Tested on NVIDIA Jetson AGX Xavier 16G and NVIDIA Jetson Xavier NX with [JetPack](https://developer.nvidia.com/embedded/jetpack) v5.1.2.

  

## General environment

  

Maximize performance:

```bash
sudo  jetson_clocks
export  MAKEFLAGS="-j$(nproc)"
```

  

Install must have utilities:

```bash
sudo  apt  update
sudo  apt  install  -y  python3-pip  python3-dev  \
git gitk cmake gcc \
default-jdk  vlc  audacity
```

  

[jtop](https://github.com/rbonghi/jetson_stats) requires reboot after installation:

```bash
sudo  -H  pip3  install  -U  jetson-stats
```

  

## Apache (Py)Arrow

Compilation instructions were tested for version 11.0.0. Plasma store has been removed from subsequent versions.

Download the source artifacts for v11.0.0 from https://arrow.apache.org/release.  

From source code directory execute:

  

### Install dependencies

  

System packages:

```bash
sudo  apt  install  -y  libjemalloc-dev  libboost-dev  \
libboost-filesystem-dev \
libboost-system-dev  \
libboost-regex-dev \
autoconf  flex  bison
```

  

Python packages:

```bash
pip3  install  cython
pip3  install  -r  python/requirements-build.txt
```

  

### Build Arrow C++ libraries

  

Setup:

```bash
mkdir  dist
export  ARROW_HOME=$(pwd)/dist
export  LD_LIBRARY_PATH=$(pwd)/dist/lib:$LD_LIBRARY_PATH
```

  

Configure:

```bash
mkdir  cpp/build
pushd cpp/build
cmake  -DCMAKE_INSTALL_PREFIX=$ARROW_HOME  \
-DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_BUILD_TYPE=release \
-DARROW_WITH_BZ2=ON  -DARROW_WITH_ZLIB=ON  \
-DARROW_WITH_ZSTD=ON -DARROW_WITH_LZ4=ON \
-DARROW_WITH_SNAPPY=ON  -DARROW_WITH_BROTLI=ON  \
-DARROW_PARQUET=ON -DARROW_PYTHON=ON \
-DARROW_PLASMA=ON  -DARROW_CUDA=ON  \
-DARROW_BUILD_TESTS=OFF -DPYTHON_EXECUTABLE=`which python3` \
..
```

  

Compile and install:

```bash
make  -j  $(nproc)
make  install
popd
```

  

Add library path to .bashrc:

```bash
echo "export LD_LIBRARY_PATH=${ARROW_HOME}/lib:\$LD_LIBRARY_PATH" >> ~/.bashrc
```

  

### Build PyArrow

  

Configure:

```bash
export  Plasma_DIR=./dist/lib/cmake/Plasma
export  Parquet_DIR=./dist/lib/cmake/Parquet
export  Arrow_DIR=./dist/lib/cmake/Arrow
export  ArrowCUDA_DIR=./dist/lib/cmake/ArrowCUDA
cd  python
export  PYARROW_WITH_PARQUET=1
export  PYARROW_WITH_PLASMA=1
export  PYARROW_WITH_CUDA=1
export  ARROW_ARMV8_ARCH=armv8-a
```

  

Build and install:

```
sudo -E bash -c "python3 setup.py install"
```
Alternatives:

```bash
pip3  install  wheel
python3  setup.py  build_ext  --build-type=release  \
--bundle-arrow-cpp bdist_wheel
pip3  install  `ls dist/*.whl`
# Or
python3  setup.py  build_ext  --inplace
```

  

More info at https://arrow.apache.org/docs/developers/python.html#python-development.

  

To lauch Plasma Store with 3G of memory use:

```
plasma_store -m 3000000000 -s /tmp/plasma
```

  

## REIP SDK

  

### Install Dependencies

  

Install the relevant version of tflite-runtime from https://google-coral.github.io/py-repo/tflite-runtime:

```bash
pip install tflit
```

  

Or full TensorFlow from [NVIDIA](https://docs.nvidia.com/deeplearning/frameworks/install-tf-jetson-platform/index.html) if tflite-runtime is not enough for tflit in tflite:

```bash
sudo  apt-get  update
sudo  apt-get  install  libhdf5-serial-dev  hdf5-tools  libhdf5-dev  zlib1g-dev  zip  libjpeg8-dev  liblapack-dev  libblas-dev  gfortran
sudo  pip3  install  -U  pip  testresources  setuptools==49.6.0
sudo  pip3  install  -U  --no-deps  numpy==1.19.4  future==0.18.2  mock==3.0.5  keras_preprocessing==1.1.2  keras_applications==1.0.8  gast==0.4.0  protobuf  pybind11  cython  pkgconfig
# sudo env H5PY_SETUP_REQUIRES=0 pip3 install -U h5py==3.1.0
sudo  pip3  install  --pre  --extra-index-url  https://developer.download.nvidia.com/compute/redist/jp/v461  tensorflow
```  

Intel TBB from sources for numba as part of librosa in audio:

```bash
git  clone  https://github.com/wjakob/tbb.git
mkdir  tbb/build
pushd tbb/build
cmake  ..
make  -j  `nproc`
sudo  make  install
popd
pip3  install  --upgrade  colorama
```

  

Additionally, llvmlite for librosa in audio:

```bash
sudo  apt-get  install  -y  llvm-10
export  LLVM_CONFIG=/usr/lib/llvm-10/bin/llvm-config
```

Additional Libraries for Audio:
 ```bash 
 sudo apt-get install portaudio19-dev gfortran libopenblas-dev liblapack-dev ffmpeg 
 pip install pyaudio 
 pip install sounddevice 
 pip install librosa
 pip install pyalsaaudio 
```  
(In smart-filter only pyalsaaudio among the pip installlables is used, however, there is legacy code with old imports in other dependencies that throws errors)

Finally, jetson-inference for GPU-accelerated blocks in video:

```bash
sudo  apt-get  update
sudo  apt-get  install  git  cmake  libpython3-dev  python3-numpy
git  clone  --recursive  --depth=1  https://github.com/dusty-nv/jetson-inference
cd  jetson-inference
mkdir  build
cd  build
cmake  ../
make  -j$(nproc)
sudo  make  install
sudo  ldconfig
```

  

### Build SDK

  

From within the desired installation directory:

  

Acquire:

```bash
git  clone  https://github.com/reip-project/reip-pipelines.git
```

  

Install:

```bash
pip3  install  -e  ./reip-pipelines
```

  

Include block libraries:

```bash
pip3  install  -e  ./reip-pipelines[audio,vis]
```

  

Full list of block libraries:
- plasma
- tflite
- audio
- video
- encrypt
- vis
- docs

*Note: JetPack has OpenCV installed already, so don't overide it by acident when installing video library! One can test OpenCV installation by running:*

```bash
python3  -c  'import cv2; print(cv2.getBuildInformation()); exit()'
```

*Also, plasma is installed by default as part of pyarrow compilation.*

  

More details at https://wp.nyu.edu/reip.

  

##### Python Bindings for gstreamer:

```bash
sudo  apt  install  -y  python3-pip  libcairo2-dev
pip3  install  git+https://github.com/jackersson/gstreamer-python.git
```

### Benchmark

  

Evaluate performance of different serialization strategies:

  
```bash
pip3  install  tqdm  matplotlib
plasma_store  -m  3000000000  -s  /tmp/plasma &
cd  reip-pipelines/examples
python3  benchmark.py  run
python3  benchmark.py  plot
```

  

The results will be saved to benchmark_results subfolder.


# Microcontroller Setup (for syncing using radio)

## How to configure CCS project using Action OS:

<ul>

<li>(Linux) Download udev rules file from [here](https://energia.nu/guide/install/linux/)
<li>Edit the file to add rules for regular usb port (it only has debug port by default) - Add: <br>SUBSYSTEM=="usb",ENV{DEVTYPE}=="usb_device",ATTRS{idVendor}=="1cbe",ATTRS{idProduct}=="0003",MODE:="0666" </li>

<li> Open a terminal and execute the following command: </li>

sudo mv /71-ti-permissions.rules /etc/udev/rules.d/

<li> Repeat the above on jetson </li>

</li>  </ul>

<li> Create new Empty CCS Project (with main.c):

Target: Tiva TM4C123GH6PM (Tiva C Series)

Connection: Stellaris In-Circuit Debug Interface 

Compiler: TI vXX.X.X LTS 
</li>

<li>Rename main.c to main.cpp (to invoke C++ compiler for main instead of C) </li>

<li>Import File System (RHM on the project) from Action OS installation directory (./aos and ./devices) with Create links in workspace enabled </li>

<li>Add the following in tm4c123gh6pm.cmd after ".init_array : > FLASH:" ->

<br>.ARM.extab : > FLASH

<br>.ARM.exidx : > FLASH </li>

<li> Configure project properties (RHM on the project): <br>

<ul>

<li>Resource -> Linked Resources: Add TIVA_WARE_ROOT=<path  to  TivaWare>  </li>

<li>Build -> ARM Compiler -> Include Options: Add ${TIVA_WARE_ROOT} and ${PROJECT_ROOT}/<path  to  Action  OS  installation  folder>  </li>

<li> Build -> ARM Compiler -> Advanced Options -> Language Options: Enable C++ exception handling (--exceptions) and C++14 dialect </li>

<li> Build -> ARM Linker -> Basic Options: Set heap size to 25600 bytes and system stack size to 2048 bytes </li>

<li> Build -> ARM Linker -> File Search Path: Add <br>${TIVA_WARE_ROOT}/driverlib/ccs/Debug/driverlib.lib,

<br>${TIVA_WARE_ROOT}/usblib/ccs/Debug/usblib.lib and

<br>${TIVA_WARE_ROOT}/grlib/ccs/Debug/grlib.lib (optional)</li>  </ul></li>

<li>Repeat Configure project properties steps for both Release and Debug modes </li>

<li>Replace content of main.cpp with your firmware </li>

<li>Compile the firmware and program the device:

<br>Run -> Debug (F11) to compile and program

<br>Run -> Resume (F8) to start execution

<br>Run -> Terminate (Ctrl + F12) to disconnect (device will keep running) </li>

<li>Power cycle the device to check that your program is running automatically</li>

</ul>

<!-- Edit the udev rules part, elaborate on what rule needs to be changed. Talk about changes to the microcontroller firmware where it returned more values than expected by the software code. Talk about pin outs and connections for microcontroller and mchstreamer, add links to firmware-->

