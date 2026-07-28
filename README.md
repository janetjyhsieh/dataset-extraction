# *FairGround*: Automated Pipeline and Generalization to Image Data

This repository contains the source code and evaluation for the automated pipeline introduced in the FairGround paper. 

## Install the package
Install dataset-extraction package using the following steps:
1. Git clone this repository.
2. `cd dataset-extraction`
3. `pip install .` (use `pip install -e .` to install in editable mode)

## Paper Evaluation Results
The Python Notebooks in `notebooks` shows how we obtained the evaluation results of the automated pipeline.

## Run the pipeline
### Literature download
To download literature to run the automated FairGround pipeline on, use the following command:
```
python -m dataset_extraction.literature.main --source openreview --venue NeurIPS.cc/2024/Conference --year 2024 --working-dir papers/refactor --keywords face facial
```