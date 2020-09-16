#

# update package lists
sudo apt-get update

# Enable immediate history (add to .bashrc)
echo 'export PROMPT_COMMAND="history -a;$PROMPT_COMMAND"' >> ~/.bashrc
. ~/.bashrc

# install python and pip
sudo apt-get install -y python3-pip python3-dev
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.6 4
sudo update-alternatives --install /usr/bin/python python /usr/bin/python2.7 1
sudo update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 4
pip install -U setuptools pip

sudo apt-get install htop

# Install jtop from jetson-stats (https://github.com/rbonghi/jetson_stats)
sudo pip install -U jetson-stats

# Optimize performance
sudo jetson_clocks

##########
# OpenCV
##########

# resize swap
sudo swapoff -a
sudo dd if=/dev/zero of=/swapfile bs=1G count=8
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
/swapfile none swap sw 0 0
grep SwapTotal /proc/meminfo

# # build
# dpkg -l | grep libopencv
# python -c 'import cv2;print(cv2.getBuildInformation())'
# git clone https://github.com/JetsonHacksNano/buildOpenCV
# cd buildOpenCV
# ./buildOpenCV.sh |& tee openCV_build.log
#
# python -c 'import cv2;print(cv2.getBuildInformation())'

###########
# pyarrow
###########

# apache arrow

# install dependencies
sudo apt-get install -y \
    libjemalloc-dev libboost-dev libboost-filesystem-dev libboost-system-dev \
    libboost-regex-dev autoconf flex bison libssl-dev curl cmake \
    llvm-10 llvm-7 clang

# get arrow source and unzip
wget https://github.com/apache/arrow/archive/apache-arrow-0.15.1.zip
unzip apache-arrow-0.15.1.zip
cd arrow-apache-arrow-0.15.1/cpp/
mkdir -p build && cd build

# build
cmake -DCMAKE_INSTALL_PREFIX=/usr/local/lib -DCMAKE_INSTALL_LIBDIR=libarrow \
    -DARROW_FLIGHT=ON -DARROW_GANDIVA=ON -DARROW_ORC=ON -DARROW_WITH_BZ2=ON \
    -DARROW_WITH_ZLIB=ON -DARROW_WITH_ZSTD=ON -DARROW_WITH_LZ4=ON \
    -DARROW_WITH_SNAPPY=ON -DARROW_WITH_BROTLI=ON -DARROW_PARQUET=ON \
    -DARROW_PYTHON=ON -DARROW_PLASMA=ON -DARROW_CUDA=ON -DARROW_BUILD_TESTS=ON \
    -DPYTHON_EXECUTABLE=/usr/bin/python3  ..
sudo jetson_clocks
make -j 3

# watch a movie.

# install arrow
sudo make install
echo 'export LD_LIBRARY_PATH=/usr/local/lib/libarrow:$LD_LIBRARY_PATH' >> ~/.bashrc
. ~/.bashrc

# pyarrow

# # install dependencies
# pip install six cython pytest psutil

# Watch another movie (i guess )

# install
cd ../python
virtualenv pyarrow-build
source ./pyarrow-build/bin/activate
pip install -r requirements-build.txt
export PYARROW_WITH_FLIGHT=1
export PYARROW_WITH_GANDIVA=1
export PYARROW_WITH_ORC=1
export PYARROW_WITH_PARQUET=1
export PYARROW_WITH_CUDA=1
export PYARROW_WITH_PLASMA=1
export ARROW_ARMV8_ARCH=armv8-a
export ARROW_LIB_DIR=/usr/local/lib/libarrow
python setup.py install
deactivate
# rm -r ./pyarrow-build/

# test
python -c 'from pyarrow import plasma' && echo 'YAY!' || echo 'Nooooo......'
