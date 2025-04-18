from setuptools import setup, find_packages

setup(
    name="petdeface",
    version="0.2.2",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'petdeface': ['data/*', 'data/*/*', 'data/*/*/*'],
    },
    install_requires=[
        'nibabel',
        'numpy',
    ],
) 