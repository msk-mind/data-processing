"""
Data Transfer / Unpack binaries
- load feature table
- get binaries out into png
- rename pngs
- column_name/accession#/instance#.png
"""
import os, time
import click
import pandas as pd
from PIL import Image 
from io import BytesIO
from pyspark.sql.functions import countDistinct

from data_processing.common.config import ConfigSet
from data_processing.common.sparksession import SparkConfig
from data_processing.common.custom_logger import init_logger
import data_processing.common.constants as const


logger = init_logger()
logger.info("Starting data_processing.radiology.feature_table.unpack")


@click.command()
@click.option('-f', '--config_file', default='config.yaml', required=True, 
    help="path to config file containing application configuration. See config.yaml.template")
@click.option('-t', '--data_config_file', default='data_processing/radiology/feature_table/config.yaml', required=True,
    help="path to data configuration file. See data_processing/radiology/feature_table/config.yaml.template")
def cli(config_file, data_config_file):
    """
    This module unpacks embedded png binaries from the given table and saves the pngs at the destination.
 
    This module is to be run from the top-level data-processing directory using the -m flag as follows:

    Example:
    $ python3 -m data_processing.radiology.feature_table.unpack \
        --data_config_file data_processing/radiology/feature_table/config.yaml \
        --config_file config.yaml
    """
    start_time = time.time()

    cfg = ConfigSet(name=const.APP_CFG, config_file=config_file)
    cfg = ConfigSet(name=const.DATA_CFG, config_file=data_config_file)

    binary_to_png(cfg)

    logger.info("--- Finished in %s seconds ---" % (time.time() - start_time))

def binary_to_png(cfg):
    """
    Load given table, unpack dicom, overlay images and save t.
    """
    spark = SparkConfig().spark_session(config_name=const.APP_CFG, app_name='unpack')
    spark.conf.set('spark.sql.execution.arrow.pyspark.enabled','false')
    table_path = const.TABLE_LOCATION(cfg)
    df = spark.read.format("delta").load(table_path)

    DESTINATION_PATH = cfg.get_value(path=const.DATA_CFG+"::DESTINATION_PATH")
    COLUMN_NAME = cfg.get_value(path=const.DATA_CFG+"::COLUMN_NAME")
    IMAGE_WIDTH = int(cfg.get_value(path=const.DATA_CFG+"::IMAGE_WIDTH"))
    IMAGE_HEIGHT = int(cfg.get_value(path=const.DATA_CFG+"::IMAGE_HEIGHT"))

    # create destination directory
    os.makedirs(DESTINATION_PATH, exist_ok=True)

    # find edge cases with more than 1 annotations
    # (sometimes both L/R organs have tumor, and we end up with 2 annotations per accesion.)
    multiple_annotations = df.groupby("metadata.AccessionNumber") \
        .agg(countDistinct("scan_annotation_record_uuid").alias("count")) \
        .filter("count > 1").toPandas()

    multiple_cases = multiple_annotations['AccessionNumber'].to_list()

    # unpack COLUMN_NAME
    for index, row in df.toPandas().iterrows():
        # mode set to L for b/w images, RGB for colored images.
        if "dicom" == COLUMN_NAME.lower():
            mode = "L"
        if "overlay" == COLUMN_NAME.lower():
            mode = "RGB"

        image = Image.frombytes(mode, (IMAGE_WIDTH, IMAGE_HEIGHT), bytes(row[COLUMN_NAME]))

        image_dir = os.path.join(DESTINATION_PATH, COLUMN_NAME, row["metadata"]["AccessionNumber"])

        if row["metadata"]["AccessionNumber"] in multiple_cases and row.label:
            image_dir = os.path.join(DESTINATION_PATH, COLUMN_NAME, row["metadata"]["AccessionNumber"] + "_" + row.label)

        os.makedirs(image_dir, exist_ok=True)

        # save image to png
        image.save(os.path.join(image_dir, str(row["metadata"]["InstanceNumber"])+".png"))

if __name__ == "__main__":
    cli()

