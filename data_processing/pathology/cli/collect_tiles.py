'''
Created: February 2021
@author: aukermaa@mskcc.org

Given a slide (container) ID
1. resolve the path to the WsiImage and TileLabels
2. perform various scoring and labeling to tiles
3. save tiles as a parquet file with schema [address, coordinates, *scores, *labels ]

Example:
python3 -m data_processing.pathology.cli.collect_tiles \
    -c TCGA-BRCA \
    -s tcga-gm-a2db-01z-00-dx1.9ee36aa6-2594-44c7-b05c-91a0aec7e511 \
    -m data_processing/pathology/cli/example_collect_tiles.json
'''

# General imports
import os, json, sys
import click

# From common
from data_processing.common.custom_logger   import init_logger
from data_processing.common.utils           import get_method_data
from data_processing.common.Container       import Container
from data_processing.common.Node            import Node
from data_processing.common.config          import ConfigSet

from data_processing.pathology.common.preprocess      import save_tiles_parquet

logger = init_logger("visualize_tile_labels.log")
cfg = ConfigSet("APP_CFG",  config_file="config.yaml")

@click.command()
@click.option('-c', '--cohort_id',    required=True)
@click.option('-s', '--container_id', required=True)
@click.option('-m', '--method_param_path',    required=True)
def cli(cohort_id, container_id, method_param_path):
    with open(method_param_path) as json_file:
        method_data = json.load(json_file)
    visualize_tile_labels_with_container(cohort_id, container_id, method_data)

def visualize_tile_labels_with_container(cohort_id: str, container_id: str, method_data: dict):
    """
    Using the container API interface, visualize tile-wise scores
    """

    # Do some setup
    container = Container( cfg ).setNamespace(cohort_id).lookupAndAttach(container_id)

    method_id            = method_data.get("job_tag", "none")
    output_container_id  = method_data.get("output_container")

    image_node  = container.get("wsi", method_data['input_wsi_tag']) 
    label_node  = container.get("TileScores", method_data['input_label_tag']) 

    # Add properties to method_data
    method_data.update(label_node.properties)

    try:
        if image_node is None:
            raise ValueError("Image node not found")

        # Data just goes under namespace/name
        # TODO: This path is really not great, but works for now
        output_dir = os.path.join(os.environ['MIND_GPFS_DIR'], "data", container._namespace_id, container._name, method_id)
        if not os.path.exists(output_dir): os.makedirs(output_dir)

        properties = save_tiles_parquet(str(image_node.path), str(label_node.path),output_dir, method_data )

    except Exception:
        container.logger.exception ("Exception raised, stopping job execution.")
    else:
        #parquet_container = Container( cfg ).setNamespace(cohort_id).lookupAndAttach(output_container_id)

        output_node = Node("TileImages", method_id, properties)
        logger.info(output_node) 
        container.add(output_node)
        container.saveAll()


if __name__ == "__main__":
    cli()