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
        'numpy',
        # audio
        'pyaudio',
        # 'soundfile',
        'librosa',
        'tflite',
        # plotting
        'matplotlib',
        # utils
        # 'pycrypto',
        # general
        # 'ray',
        # 'readi',
        # 'confuse@https://github.com/beetbox/confuse/archive/master.zip',
        'fire',
    ],
    extras_require={
        'docs': ['sphinx!=1.3.1', 'sphinx_theme', 'sphinx-gallery'],
    },
    license='MIT License',
    keywords='')
