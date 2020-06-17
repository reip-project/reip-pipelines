import setuptools

USERNAME = 'reip-project'
NAME = 'reip'

setuptools.setup(
    name=NAME,
    version='0.0.1',
    description='',
    long_description=open('README.md').read().strip(),
    long_description_content_type='text/markdown',
    author='Bea Steers',
    author_email='bea.steers@gmail.com',
    url='https://github.com/{}/{}'.format(USERNAME, NAME),
    packages=setuptools.find_packages(),
    # entry_points={'console_scripts': ['{name}={name}:main'.format(name=NAME)]},
    install_requires=[
        'numpy',
        'pyaudio',
        'librosa',
        'readi',
        'tflite',
        'ray',
        'confuse@https://github.com/beetbox/confuse/archive/master.zip',
        'pycrypto',
        'fire',
    ],
    extras_require={
        'docs': ['sphinx!=1.3.1', 'sphinx_theme', 'sphinx-gallery'],
    },
    license='MIT License',
    keywords='')
