#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="sotlas",
    version="1.0.0rc1",
    author="Hiago Pinho",
    license="Apache-2.0 WITH LLVM-exception",
    package_dir={"": "compiler"},
    packages=find_packages(where="compiler"),
    entry_points={
        "console_scripts": [
            "sotlas=sotlas.driver:main",
            "sotlasc=sotlas.driver:main",
            "sotlas-lsp=sotlas_compile.lsp:main",
        ],
    },
)
