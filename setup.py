import os
from setuptools import setup

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()


setup(
    name='kimo',
    version=open("kimo/_version.py").readlines()[-1].split()[-1].strip("\"'"),
    packages=['kimo'],
    python_requires='>=3.5.2',
    install_requires=[
        'requests>=2',
        'Flask>=0.12',
        'psutil>=2',
        'terminaltables>=3',
        'mysql-connector>=2.1,<2.2',
        'waitress>=1',
    ],
    include_package_data=True,
    license='BSD License',
    description='Finds owner processes of MySQL queries.',
    long_description=README,
    keywords='kimo mysql query monitor diagnostic',
    url='https://github.com/putdotio/kimo',
    author='Omer Murat Yildirim, Cenk Alti',
    author_email='omermuratyildirim@gmail.com, cenkalti@gmail.com',
    entry_points={
        'console_scripts': [
            'kimo = kimo.cli:main',
            'kimo-server = kimo.server:main',
        ]
    }
)
