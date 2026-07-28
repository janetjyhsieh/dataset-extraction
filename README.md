# *FairGround*: Semi-Automatic Extension to Image Data

This repository contains the source code and evaluation for the (semi-)automated usage extraction and metadata annotation pipeline introduced in the FairGround paper. 

## Install the package
Install dataset-extraction package using the following steps:
1. Git clone this repository.
2. `cd dataset-extraction`
3. `pip install .` (use `pip install -e .` to install in editable mode)

## Paper Evaluation Results
The Python Notebooks in `notebooks` shows how we obtained the evaluation results of the automated pipeline.

## Run the pipeline
### Literature download
To download literature to run the automated FairGround pipeline on, run the following command:
```
python -m dataset_extraction.literature.main \
    --working-dir papers/neurips-2024-face \
    --source openreview \
    --venue NeurIPS.cc/2024/Conference \
    --year 2024 \
    --keywords face facial
```
The above command creates a working directory `papers/neurips-2024-face` and download NeurIPS 2024 papers with "face" or "facial" keywords. Change these input arguments to download custom literature for analysis.

### Run the automatic pipeline
To run the automatic pipeline on the downloaded literature, run the following command and provide the working directory containing the literature (downloaded to in the previous step).
```
python -m dataset_extraction.fairground.main \
    --working-dir papers/neurips-2024-face
```

After running the command, you can find the final annotated dataset table `dataset_table.csv` in the `working-dir/fg/output/` directory. In the directory, there is also the intermediate usage extraction output `dataset_usage_table.csv`.

#### Manual Augmentation
The automatic usage extraction and metadata annotation pipeline ouputs an dataset table with metadata annotations. However, there may still be empty fields where the LLM abstains from answering and some errors. Manual annotators can veryfy and add additional annotations as needed. This whole process is the semi-automatic extension to the Fairground pipeline.