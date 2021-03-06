import os, shutil, sys
import pytest
from click.testing import CliRunner

from data_processing.common.config import ConfigSet
import data_processing.common.constants as const

from data_processing.clinical.proxy_table.generate import generate_proxy_table, cli
from data_processing.common.sparksession import SparkConfig

project_path = 'tests/data_processing/clinical/testdata/test-project'
clinical_proxy_table = 'tests/data_processing/clinical/testdata/test-project/tables/TEST_CLINICAL_PATIENTS_20210308'
app_config_path = 'tests/data_processing/clinical/testdata/test-project/config/TEST_CLINICAL_PATIENTS_20210308/app_config.yaml'
data_config_path = 'tests/data_processing/clinical/testdata/test-project/config/TEST_CLINICAL_PATIENTS_20210308/data_config.yaml'


@pytest.fixture(autouse=True)
def spark():
    print('------setup------')
    cfg = ConfigSet(name=const.APP_CFG, config_file='tests/test_config.yaml')
    spark = SparkConfig().spark_session(config_name=const.APP_CFG, app_name='test-clinical-proxy-preprocessing')

    yield spark

    print('------teardown------')
    if os.path.exists(project_path):
        shutil.rmtree(project_path)


def test_generate_proxy_table_tsv(spark):

    cfg = ConfigSet(name=const.DATA_CFG, config_file='tests/data_processing/clinical/testdata/data_tsv_config.yaml')

    generate_proxy_table()

    df = spark.read.format('delta').load(clinical_proxy_table)
    assert df.count() == 3
    df.unpersist()

def test_generate_proxy_table_csv(spark):

    cfg = ConfigSet(name=const.DATA_CFG, config_file='tests/data_processing/clinical/testdata/data_csv_config.yaml')

    generate_proxy_table()

    df = spark.read.format('delta').load(clinical_proxy_table)
    assert df.count() == 3
    df.unpersist()


def test_generate_proxy_table_error():

    cfg = ConfigSet(name=const.DATA_CFG, config_file='tests/data_processing/clinical/testdata/data_error_config.yaml')

    with pytest.raises(Exception, match=r'Make sure input file is a valid tsv or csv file'):
        generate_proxy_table()


def test_cli(spark):
    runner = CliRunner()
    result = runner.invoke(cli, [
        '-d', 'tests/data_processing/clinical/testdata/data_tsv_config.yaml',
        '-a', 'tests/test_config.yaml'])
    assert result.exit_code == 0

    assert os.path.exists(app_config_path)
    assert os.path.exists(data_config_path)

    df = spark.read.format('delta').load(clinical_proxy_table)
    assert df.count() == 3
    df.unpersist()

