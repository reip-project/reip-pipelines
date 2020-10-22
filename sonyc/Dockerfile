FROM balenalib/raspberrypi3-debian:buster-build as builder

ARG MAKE_JOBS=1
ARG ARROW_VERSION=0.17.1

RUN install_packages \
        autoconf \
        bison \
        ca-certificates \
        cmake \
        curl \
        cython3 \
        flex \
        g++ \
        gcc \
        libboost-dev \
        libboost-filesystem-dev \
        libboost-regex-dev \
        libboost-system-dev \
        libjemalloc-dev \
        libssl-dev \
        make \
        ninja-build \
        pkg-config \
        python3-dev \
        python3-numpy \
        python3-pandas \
        python3-pip \
        python3-psutil \
        python3-setuptools \
        python3-six \
        python3-wheel \
        rapidjson-dev \
        tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build/arrow
RUN curl --silent --show-error --fail --location \
      https://github.com/apache/arrow/archive/apache-arrow-${ARROW_VERSION}.tar.gz \
  | tar --strip-components=1 -xz

ENV ARROW_HOME=/dist
ENV CMAKE_BUILD_PARALLEL_LEVEL=${MAKE_JOBS}

WORKDIR /build/arrow/cpp/release
RUN cmake -G Ninja \
          -DCMAKE_INSTALL_PREFIX=${ARROW_HOME} \
          -DCMAKE_INSTALL_LIBDIR=lib \
          -DCMAKE_SHARED_LINKER_FLAGS="-latomic" \
          -DPYTHON_EXECUTABLE=/usr/bin/python3 \
          -DARROW_BUILD_STATIC=OFF \
          -DARROW_DEPENDENCY_SOURCE=SYSTEM \
          -DARROW_ENABLE_TIMING_TESTS=OFF \
          -DARROW_HOME=/dist \
          -DARROW_PLASMA=ON \
          -DARROW_PYTHON=ON \
          -DARROW_RPATH_ORIGIN=ON \
          -DARROW_USE_LD_GOLD=ON \
          .. \
 && ninja install

ENV PYARROW_CMAKE_GENERATOR=Ninja
ENV PYARROW_CMAKE_OPTIONS="-DARROW_USE_LD_GOLD=ON"
ENV PYARROW_WITH_PLASMA=1
ENV PYARROW_BUNDLE_ARROW_CPP=1

WORKDIR /build/arrow/python
RUN python3 setup.py build_ext bdist_wheel

#FROM balenalib/raspberrypi3-debian:buster
FROM balenalib/raspberrypi3-debian-python:3.7.4
COPY --from=builder /build/arrow/python/dist/pyarrow-*.whl /dist/

RUN apt-get -q update && \
    apt-get install -y portaudio19-dev alsa-utils \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get -q update && \
    apt-get install -y llvm-9-dev \
    && rm -rf /var/lib/apt/lists/*
ENV LLVM_CONFIG /usr/bin/llvm-config-9
RUN apt-get -q update && \
    apt-get install -y libffi-dev libatlas-base-dev libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
#RUN apt-get -q update && \
#    apt-get install -y make \
#    && rm -rf /var/lib/apt/lists/*

# RUN pip install reip

COPY requirements.txt .
RUN apt-get -q update && apt-get install -qy build-essential && \
    pip install -r ./requirements.txt --no-cache-dir --extra-index-url https://www.piwheels.org/simple \
    && apt-get remove -y build-essential && rm -rf /var/lib/apt/lists/*

RUN pip install psutil ixconfig remoteobj==0.2.6  --upgrade

WORKDIR /app
COPY *.py .

#RUN apt-get -q update && \
#    apt-get install -y libatlas-base-dev libsndfile1 \
#    && rm -rf /var/lib/apt/lists/*

#COPY ../ /reip
#RUN pip install -e /reip --no-deps
RUN python -m tflit.tflite_install
ENTRYPOINT pip install /reip --no-deps && python node.py
#CMD python node.py
