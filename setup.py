from setuptools import setup

setup(
    name="alienware-lights",
    version="1.0.0",
    description="RGB light controller for Alienware x15 R1 on Linux",
    author="arkrnr",
    py_modules=["alienware_lights"],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "alienware-lights=alienware_lights:main",
        ],
    },
    classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Hardware",
    ],
)
