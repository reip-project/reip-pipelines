import setuptools

USERNAME = 'reip-project'
NAME = 'reip'

setuptools.setup(
    name=NAME,
    version='0.0.1',
    description='',
    long_description=open('README.md').read().strip(),
    long_description_content_type='text/markdown',
    author='Bea Steers, Yurii Piadyk',
    author_email='bea.steers@gmail.com',
    url='https://github.com/{}/{}'.format(USERNAME, NAME),
    packages=setuptools.find_packages(),
    # entry_points={'console_scripts': ['{name}={name}:main'.format(name=NAME)]},
    install_requires=[
        # cli
        'fire', 'colorlog',
        # core packages
        'numpy',
        'remoteobj>=0.2.6',
        # 'pyarrow',
        # block packages
        'watchdog', 'tflit>=0.0.13',
        # status messages
        'psutil', 'ifcfg', 'ixconfig>=0.1.1', 'netswitch', 'requests',
    ],
    extras_require={
        # 'status': ['psutil', 'ixconfig', 'netswitch'],
        'audio': ['sounddevice', 'librosa'],
        'video': ['opencv-python'],  # already installed on Jetson by default
        'encrypt': ['pycrypto'],
        'vis': ['matplotlib'],
        'docs': ['sphinx!=1.3.1', 'sphinx_theme', 'sphinx-gallery'],
    },
    license='BSD 3-Clause Clear License',
    keywords='iot embedded app pipeline block multiprocessing')
