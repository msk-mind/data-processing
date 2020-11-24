import pytest
from pytest_mock import mocker
import os
from click.testing import CliRunner

from data_processing.common.config import ConfigSet
from data_processing.common.sparksession import SparkConfig
from data_processing.common.Neo4jConnection import Neo4jConnection
from data_processing.dicom_to_graph import update_graph_with_scans, cli

current_dir = os.getcwd()

@pytest.fixture(autouse=True)
def spark():
    print('------setup------')
    APP_CFG = 'APP_CFG'
    ConfigSet(name=APP_CFG, config_file='tests/test_config.yaml')
    spark = SparkConfig().spark_session(config_name=APP_CFG, app_name='test-dicom-to-graph')

    yield spark

    print('------teardown------')


def test_cli(mocker, spark, monkeypatch):
    # setup env
    monkeypatch.setenv("MIND_ROOT_DIR", current_dir+"/tests/data_processing/testdata/data")
    monkeypatch.setenv("MIND_WORK_DIR", current_dir+"/tests/data_processing/testdata/work")

    # mock neo4j
    mocker.patch('data_processing.common.Neo4jConnection.Neo4jConnection')
    mocker.patch.object(Neo4jConnection, 'query')
    Neo4jConnection.query.return_value = []

    runner = CliRunner()
    result = runner.invoke(cli, ['-s', 'local[2]',
                                 '-g', 'bolt://localhost:7883',
                                 '-h', 'file:///',
                                 '-f', 'tests/test_config.yaml'])

    assert result.exit_code == 0
    # radiology.dcm in testdata has only 1 row
    Neo4jConnection.query.assert_called_once()
