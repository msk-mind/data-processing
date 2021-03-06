'''
Created on September 11, 2020

@author: pashaa@mskcc.org

This module generates a delta table for clinical data stored in a csv or tsv file with tab delimiters.
'''
import click
import os, shutil

from data_processing.common.CodeTimer import CodeTimer
from data_processing.common.config import ConfigSet
from data_processing.common.custom_logger import init_logger

from pyspark.sql.functions import expr
from pyspark.sql.utils import AnalysisException

from data_processing.common.sparksession import SparkConfig
import data_processing.common.constants as const

logger = init_logger()

def generate_proxy_table():

    cfg = ConfigSet()
    spark = SparkConfig().spark_session(config_name=const.APP_CFG, app_name="data_processing.clinical.proxy_table.generate")

    logger.info("generating proxy table...")
    source_path = cfg.get_value(path=const.DATA_CFG+'::SOURCE_PATH')
    file_ext = cfg.get_value(path=const.DATA_CFG+'::FILE_TYPE')

    delimiter = ''
    if file_ext and file_ext.lower() == 'csv':
        delimiter = ','
    elif file_ext and file_ext.lower() == 'tsv':
        delimiter = '\t'
    else:
        raise Exception("Make sure input file is a valid tsv or csv file")

    table_location = const.TABLE_LOCATION(cfg)

    df = spark.read.options(header='True', inferSchema='True', delimiter=delimiter).csv(source_path)
    # generate uuid
    df = df.withColumn("uuid", expr("uuid()"))

    df.coalesce(cfg.get_value(path=const.DATA_CFG+'::NUM_PARTITION')).write.format("delta"). \
        mode('overwrite'). \
        save(table_location)

    df.printSchema()
    df.show()


@click.command()
@click.option('-d', '--data_config_file', default=None, type=click.Path(exists=True),
              help="path to yaml template file containing information required for clinical proxy data ingestion. "
                   "See data_ingestion_template.yaml.template")
@click.option('-a', '--app_config_file', default='config.yaml', type=click.Path(exists=True),
              help="path to config file containing application configuration. See config.yaml.template")
def cli(data_config_file, app_config_file):
    """
    This module generates a delta table for clinical data stored in a csv or tsv file with tab delimiters.

    Example:
        python3 -m data_processing.clinical.proxy_table.generate \
                 --data_config_file <path to data config file> \
                 --app_config_file <path to app config file> \
    """
    with CodeTimer(logger, 'generate clinical proxy table'):
        # Setup configs
        cfg = ConfigSet(name=const.APP_CFG, config_file=app_config_file)
        # data_type used to build the table name can be pretty arbitrary, so left the schema file out for now.
        cfg = ConfigSet(name=const.DATA_CFG, config_file=data_config_file)

        # copy app and data configuration
        config_location = const.CONFIG_LOCATION(cfg)
        os.makedirs(config_location, exist_ok=True)

        shutil.copy(app_config_file, os.path.join(config_location, "app_config.yaml"))
        shutil.copy(data_config_file, os.path.join(config_location, "data_config.yaml"))

        generate_proxy_table()


if __name__ == "__main__":
    cli()
