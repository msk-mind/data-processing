'''
Created: February 2021
@author: aukermaa@mskcc.org

Given a scan (container) ID
1. resolve the path to a volumentric image and annotation (label) files
2. resample image and segmentation, and save voxels as a 3d numpy array (.npy)
3. store results on HDFS and add metadata to the graph

'''

# General imports
import os, json, sys
import click

# From common
from data_processing.common.custom_logger   import init_logger
from data_processing.common.utils           import get_method_data
from data_processing.common.Container       import Container
from data_processing.common.Node            import Node
from data_processing.common.config import ConfigSet

# From radiology.common
from data_processing.radiology.common.preprocess   import extract_voxels

from medpy.io import load

logger = init_logger("extractVoxels.log")
cfg = ConfigSet("APP_CFG",  config_file="config.yaml")

@click.command()
@click.option('-c', '--cohort_id',    required=True)
@click.option('-s', '--container_id', required=True)
@click.option('-m', '--method_id',    required=True)
def cli(cohort_id, container_id, method_id):
    method_data = get_method_data(cohort_id, method_id)
    extract_voxels_with_container(cohort_id, container_id, method_data)

def extract_voxels_with_container(cohort_id: str, container_id: str, method_data: dict):
    """
    Using the container API interface, extract voxels for a given scan container
    """

    # Do some setup
    container   = Container( cfg ).setNamespace(cohort_id).lookupAndAttach(container_id)
    method_id   = method_data.get("job_tag", "none")

    image_node  = container.get("mhd", method_data['image_input_tag']) 
    label_node  = container.get("mha", method_data['label_input_tag'])

    try:
        if image_node is None:
            raise ValueError("Image node not found")

        if label_node is None:
            raise ValueError("Label node not found")

        # Data just goes under namespace/name
        # TODO: This path is really not great, but works for now
        output_dir = os.path.join(os.environ['MIND_GPFS_DIR'], "data", container._namespace_id, container._name, method_id)
        if not os.path.exists(output_dir): os.makedirs(output_dir)

        properties = extract_voxels(
            image_path = str(next(image_node.path.glob("*.mhd"))),
            label_path = str(label_node.path),
            output_dir = output_dir,
            params     = method_data
        )

    except Exception:
        container.logger.exception ("Exception raised, stopping job execution.")
    else:
        output_node = Node("voxels", method_id, properties)
        container.add(output_node)
        container.saveAll()


if __name__ == "__main__":
    cli()
