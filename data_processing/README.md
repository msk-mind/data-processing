# Radiology Deep Learning Preprocessing

PoC scripts to create features based on mock Scan and Annotation tables.

### Setup

```
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### Test Dataset

Test data, along with example CSVs are on the GPFS mount.
For mock silver tables (scan, annotation), see `/gpfs/mskmind_ess/eng/radiology/dl_preprocess`
For image and segmentation data, see `/gpfs/mskmind_ess/eng/radiology/data`


### Create Mock Scan and Annotation tables in Delta format

Update the input CSV paths and delta table paths, then run:

```
python create_mock_tables.py
```


### Run preprocess job

This job
1. Reads Scan and Annotation delta tables.
2. Writes a feature table with additional columns (preprocessed_seg_path, preprocessed_img_path, preprocessed_target_spacing)
3. Resamples the image (.mhd) and segmentation (.mha) and saves the "feature files" in .npy

Make sure scan and annotation tables under {base_directory}/tables/scan and {base_directory}/tables/annotation.
Feature table and feature file location will be written under  {base_directory}/features/feature_table and {base_directory}features/feature_files.

Run:
```
python preprocess_feature.py --spark_master_uri {spark_master_uri} --base_directory {path/to/delta/table/parent/directory} --target_spacing {x_spacing} {y_spacing} {z_spacing}
```


## Generate scans
Your python and spark environement should be automatically setup at login.

Manually set some path variables; root dir is the data lake base directory /data/, while the work directory is in /tmp/.  The GPFS mount directory is given too as we've moved from hadoop for I/O.
```
export MIND_ROOT_DIR=/data/
export MIND_WORK_DIR=/tmp/working
export MIND_GPFS_DIR=/gpfs/mskmindhdp_emc/
```
### Start an IO service

Works now. Accepts a restful message from the UDF upon completition with a WRITE instruction:

`[command], [working directory path], [concept ID to attach], [record ID to ingest], [tag]`

Checks that a concept ID exists and that the record ID does not exist. Assumes record IDs look like `{datatype}-{tag}-{hash}` such that there is exactly 1 record per data type, per tag, per output.  

A node in the graph DB is created in the `PENDING` state as the delta table operations run, and then is updated to the `VALID` state upon successful completition of the write operation. If something fails, the node will remain in the `PENDING` state. 

You can see the nodes switch from pending to valid as the backlog to the service completes!
```
python3 -m data_processing.services.delta_io_service \
	--hdfs hdfs://pllimsksparky1.mskcc.org:8020 \
	--host pllimsksparky1  & 
```


### Run process scan job
```
python -m data_processing.process_scan_job \
--query "WHERE source:xnat_accession_number AND ALL(rel IN r WHERE TYPE(rel) IN ['ID_LINK'])" \
--hdfs_uri hdfs://pllimsksparky1.mskcc.org:8020 \
--custom_preprocessing_script /gpfs/mskmindhdp_emc/tmp/generateMHD.py \
--tag test
```
You should see some new folders and outputs at /tmp/working/job-ajdj3-...

The where clause is technically a modifier on the allowed types of relationship paths to which the sink ID type (SeriesInstanceUID).  In this example, we are looking for scans with an ID_LINK relationship to any xnat accession number node.

To only run on scans for which an annotation is available, use:
```
"WHERE source:annotation_record_uuid AND ALL(rel IN r WHERE TYPE(rel) IN ['HAS_RECORD'])"
```
If you run this command twice with the same tag, no change in the state of the data lake should occur.

### TODO

DONE - Take target spacing parameter, table paths as arguments (using click)
- Embed .npy in the parquet/delta tables if needed
- Using Spark UDF, foreachPartition resulted in degraded performance (~5 min) compared to using Parallel (~1 min). Investigate if there is a better way to iterate over rows in Spark.
- Performance test on Spark cluster
