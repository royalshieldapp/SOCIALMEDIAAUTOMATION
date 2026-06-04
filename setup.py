"""Setup configuration for SOCIALMEDIAAUTOMATION package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="socialmediaautomation",
    version="2.0.0",
    author="RoyalShield",
    description="FastAPI backend for automating social media posts on Facebook/Instagram with Make.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/royalshieldapp/SOCIALMEDIAAUTOMATION",
    py_modules=["SOCIALMEDIAAUTOMATION"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Framework :: FastAPI",
        "Topic :: Internet",
        "Topic :: Communications :: Email",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "flake8>=6.0",
            "pylint>=2.17",
            "isort>=5.12",
        ],
    },
)
