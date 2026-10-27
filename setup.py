from pathlib import Path

from setuptools import find_packages, setup

README = Path(__file__).with_name("README.md")
long_description = README.read_text(encoding="utf-8") if README.exists() else ""

setup(
    name="sendmail_api",
    version="2.0.0",
    description="HTTP to SMTP relay with an auditable delivery log",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.8",
    packages=find_packages(exclude=("tests", "tests.*")),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "Flask>=2.2",
        "mysql-connector-python>=8.0",
    ],
    extras_require={"test": ["pytest>=7.0"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Framework :: Flask",
        "Operating System :: OS Independent",
    ],
)
