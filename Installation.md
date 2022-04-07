# Installation of REIP SDK on NVIDIA Jetson

Tested on NVIDIA Jetson AGX Xavier 16G with [JetPack](https://developer.nvidia.com/embedded/jetpack) v4.6.1.

## General environment

Maximize performance:
```bash
sudo jetson_clocks
export MAKEFLAGS="-j$(nproc)"
```

Install must have utilities:
```bash
sudo apt update
sudo apt install -y python3-pip python3-dev \
                    git gitk cmake gcc \
                    default-jdk vlc audacity
```

[jtop](https://github.com/rbonghi/jetson_stats) requires reboot after installation:
```bash
sudo -H pip3 install -U jetson-stats
```

## Apache (Py)Arrow

Download the latest release from https://arrow.apache.org/release.
Compilation instructions were tested for version 7.0.0 (3 February 2022).

From source code directory execute:

### Install dependencies

System packages:
```bash
sudo apt install -y libjemalloc-dev libboost-dev \
                    libboost-filesystem-dev \
                    libboost-system-dev \
                    libboost-regex-dev \
                    autoconf flex bison
```

Python packages:
```bash
pip3 install -r python/requirements-build.txt
```

### Build Arrow C++ libraries

Setup:
```bash
mkdir dist
export ARROW_HOME=$(pwd)/dist
export LD_LIBRARY_PATH=$(pwd)/dist/lib:$LD_LIBRARY_PATH
```

Configure:
```bash
mkdir cpp/build
pushd cpp/build

cmake -DCMAKE_INSTALL_PREFIX=$ARROW_HOME \
        -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_BUILD_TYPE=release \
        -DARROW_WITH_BZ2=ON -DARROW_WITH_ZLIB=ON \
        -DARROW_WITH_ZSTD=ON -DARROW_WITH_LZ4=ON \
        -DARROW_WITH_SNAPPY=ON -DARROW_WITH_BROTLI=ON \
        -DARROW_PARQUET=ON -DARROW_PYTHON=ON \
        -DARROW_PLASMA=ON -DARROW_CUDA=ON \
        -DARROW_BUILD_TESTS=OFF -DPYTHON_EXECUTABLE=`which python3` \
        ..
```

Compile and install:
```bash
make -j $(nproc)
make install
popd
```

Add library path to .bashrc:
```
echo "export LD_LIBRARY_PATH=${ARROW_HOME}/lib:\$LD_LIBRARY_PATH" >> ~/.bashrc
```

### Build PyArrow

Configure:
```bash
cd python

export PYARROW_WITH_PARQUET=1
export PYARROW_WITH_PLASMA=1
export PYARROW_WITH_CUDA=1
export ARROW_ARMV8_ARCH=armv8-a
```

Build and install:
```
sudo -E bash -c "python3 setup.py install"
```

Alternatives:
```bash
pip3 install wheel
python3 setup.py build_ext --build-type=release \
        --bundle-arrow-cpp bdist_wheel
pip3 install `ls dist/*.whl`
# Or
python3 setup.py build_ext --inplace
```

More info at https://arrow.apache.org/docs/developers/python.html#python-development.

To lauch Plasma Store with 3G of memory use:
```
plasma_store -m 3000000000 -s /tmp/plasma
```

## REIP SDK

From withis the desired installation directory:

Acquire:
```bash
git clone https://github.com/reip-project/reip-pipelines.git
```

Install:
```bash
pip install -e ./reip-pipelines
```

Include block libraries:
```bash
pip install -e ./reip-pipelines[audio,video]
```

Full list of block liraries:
 - audio
 - video
 - encrypt
 - network?
 - vis

*Note: JetPack has OpenCV installed already, so don't overide it by acident when installing video library!*

More details at https://wp.nyu.edu/reip.

### Benchmark

Evaluate performance of different serialization strategies:

```bash
pip3 install tqdm matplotlib
plasma_store -m 3000000000 -s /tmp/plasma &
cd reip-pipelines/examples
python3 benchmark.py run
python3 benchmark.py plot
```

The results will be saved to benchmark_results subfolder.
