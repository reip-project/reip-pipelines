import setuptools

USERNAME = 'reip-project'
NAME = 'reip'

setuptools.setup(
    name=NAME,
    version='0.0.3',
    description='',
    long_description=open('README.md').read().strip(),
    long_description_content_type='text/markdown',
    author='Yurii Piadyk, Bea Steers',
    author_email='ypiadyk@nyu.edu',
    url='https://github.com/reip-project/reip-pipelines',
    packages=setuptools.find_packages(),
    # entry_points={'console_scripts': ['{name}={name}:main'.format(name=NAME)]},
    install_requires=[
        # cli
        'fire', 'colorlog',
        # core packages
        'numpy',
        'remoteobj>=0.3.1',
        # 'pyarrow',
        # block packages
        'watchdog',
        # 'tflit>=0.1.2',
        # status messages
        'psutil', 'ifcfg', 'ixconfig>=0.1.1', 'netswitch', 'requests',
    ],
    extras_require={
        # 'status': ['psutil', 'ixconfig', 'netswitch'],
        'plasma': ['pyarrow'],
        'tflite': ['tflit>=0.1.2'],
        'audio': ['sounddevice', 'librosa'],
        'video': ['opencv-python'],  # already installed on Jetson by default
        # 'gstream': ['PyGObject'],
        'encrypt': ['pycryptodome'],
        'vis': ['matplotlib'],
        'docs': ['sphinx!=1.3.1', 'sphinx_theme', 'sphinx_rtd_theme'],
    },
    license='BSD 3-Clause Clear License',
    keywords='iot embedded app pipeline block multiprocessing')
